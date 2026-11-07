"""Small synthetic oracle, independent of the downloaded dataset."""
import json
import tempfile
import unittest
from pathlib import Path
from recipebox.store import Store, build, FILES
from recipebox.chat import Chatbot, parse
from recipebox.normalize import canonical, quantity, steps, violations
from recipebox.matching import quantity_check
from recipebox.substitute import similarity_key


def rec(title, ingredients, instructions="Mix ingredients. Bake until done."):
    return dict(title=title,ingredients=ingredients,instructions=instructions)


class SystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        ar={
          "p1":rec("Penne Pasta",["1 cup penne pasta","1/2 cup cream","1 clove garlic"]),
          "p2":rec("Penne Pasta Tomato",["1 cup penne pasta","2 tomatoes","1 onion","1 clove garlic"],"Boil pasta.\nStir in tomato.\nServe."),
          "banana":rec("Banana Bread",["2 bananas","2 eggs","1 cup all-purpose flour","1/2 cup sugar","1 teaspoon baking soda","1/4 cup oil"]),
          "peanut":rec("Peanut Rice",["1 cup rice","1 egg","1 onion","1 tablespoon peanuts"]),
          "noise":rec("Noisy",["ADVERTISEMENT","1 cup rice ADVERTISEMENT","1 onion ADVERTISEMENT"]),
          "bad":None,
        }
        epi={
          "banana":rec("Eggless Banana Bread",["2 bananas","1/2 cup applesauce","1 cup all-purpose flour","1/2 cup sugar","1 teaspoon baking soda","1/4 cup oil"]),
          "p3":rec("Pasta with Coconut",["1 cup penne pasta","1/2 cup coconut milk","1 clove garlic"]),
          "eggwhite":rec("Foam",["2 egg whites","1 cup sugar"],"Whisk eggs. Bake."),
        }
        fn={f"r{i}":rec(f"Garlic Onion Rice {i}",["1 cup rice","1 clove garlic","1 onion","1 egg"]) for i in range(7)}
        for source,contents in [("ar",ar),("epi",epi),("fn",fn)]:
            (cls.root/FILES[source]).write_text(json.dumps(contents),encoding="utf-8")
        cls.manifest=build(cls.root,cls.root/"recipes.sqlite3")

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self): self.store=Store(self.root/"recipes.sqlite3"); self.bot=Chatbot(self.store)
    def tearDown(self): self.store.close()

    def test_all_sources_namespaced_and_preserved(self):
        self.assertEqual(self.manifest["raw_records"],16)
        self.assertEqual(self.manifest["valid_records"],15)
        self.assertNotEqual(self.store.recipe("ar:banana")["id"],self.store.recipe("epi:banana")["id"])
        r=self.store.recipe("ar:noise")
        self.assertEqual(r["ingredients"][0],"ADVERTISEMENT")
        self.assertEqual(r["ingredient_count"],2)
        self.assertEqual(self.store.recipe("ar:bad")["raw_record"],None)

    def test_all_three_required(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError): build(directory,Path(directory)/"out.db")

    def test_multi_turn_dairy_filter(self):
        first=self.bot.ask("Find a penne pasta recipe.")
        self.assertTrue(first["results"])
        second=self.bot.ask("I cannot have dairy.")
        self.assertEqual(second["filters"]["query"],"penne pasta")
        self.assertIn("dairy",second["filters"]["exclude"])
        self.assertNotIn("ar:p1",[r["id"] for r in second["results"]])
        self.assertFalse(any(violations(r["ingredients"],["dairy"]) for r in second["results"]))

    def test_aggregate_not_top_five(self):
        self.bot.ask("/search penne")
        answer=self.bot.ask("How many recipes contain both garlic and onion? What percentage of the dataset is that?")
        self.assertEqual(answer["value"],8)
        self.assertEqual(answer["denominator"],15)
        self.assertAlmostEqual(answer["percentage_of_dataset"],100*8/15)
        self.assertEqual(answer["filters"]["query"],"")
        follow=self.bot.ask("What percentage of the dataset is that?")
        self.assertEqual(follow["value"],8)

    def test_average_median_common_and_step_rank(self):
        self.bot.ask('/json {"action":"stats","include":["tomato"],"query":""}')
        average=self.bot.ask("/stats average")
        self.assertEqual(average["value"],4)
        self.assertEqual(self.bot.ask("/stats median")["value"],4)
        self.assertEqual(self.bot.ask("/stats common")["value"][0]["recipe_count"],1)
        self.assertEqual(self.bot.ask("/stats fewest_steps")["value"][0]["id"],"ar:p2")

    def test_pantry_followup_and_hard_constraints(self):
        first=self.bot.ask("I have eggs, onions, tomatoes, and rice. Suggest five recipes using as many of these as possible, with no peanuts and at most six instruction steps. Prefer recipes that need the fewest additional ingredients.")
        self.assertEqual(first["kind"],"match")
        self.assertEqual(first["filters"]["max_steps"],6)
        self.assertNotIn("ar:peanut",[x["recipe"]["id"] for x in first["results"]])
        second=self.bot.ask("Exclude eggs too")
        self.assertTrue(all(not violations(x["recipe"]["ingredients"],["egg","peanut"]) for x in second["results"]))
        self.assertEqual(second["filters"]["max_steps"],6)
        self.assertEqual(second["pantry"],first["pantry"])

    def test_no_match_never_relaxes(self):
        self.bot.ask("/search unobtainiumdragonfruit")
        self.assertEqual(self.bot.ask("/exclude dairy")["results"],[])
        self.assertEqual(self.bot.ask("/stats average")["value"],None)

    def test_quantity_sufficient_insufficient_and_unknown(self):
        r=self.store.recipe("ar:banana")
        checks=quantity_check(["1 egg","500 g all purpose flour","1 cup sugar"],r)
        statuses={x["ingredient"]:x["status"] for x in checks}
        self.assertEqual(statuses["egg"],"insufficient")
        self.assertEqual(statuses["all purpose flour"],"not_verified")
        self.assertEqual(statuses["sugar"],"sufficient")
        self.assertIsNone(quantity("1 (14 ounce) can tomatoes"))
        self.assertIsNone(quantity("1 to 2 cups sugar"))
        self.assertAlmostEqual(quantity("1 1/2 cups sugar")[1],1.5*236.5882365)

    def test_form_distinctions_and_synonyms(self):
        self.assertEqual(canonical("2 onions, finely chopped"),"onion")
        self.assertEqual(canonical("1 tablespoon extra-virgin olive oil"),"olive oil")
        self.assertNotEqual(canonical("1 tsp garlic powder"),canonical("2 cloves garlic"))
        self.assertNotEqual(canonical("2 egg whites"),canonical("2 eggs"))
        self.assertNotEqual(canonical("1 cup cooked rice"),canonical("1 cup rice"))
        self.assertNotEqual(canonical("2 tablespoons tomato paste"),canonical("2 tomatoes"))
        self.assertNotEqual(canonical("unbleached all purpose flour"),canonical("all purpose flour"))
        self.assertEqual(similarity_key("unbleached all purpose flour"),similarity_key("all purpose flour"))

    def test_substitution_evidence_and_complete_variant(self):
        self.bot.ask("/search banana bread")
        self.bot.ask("/show ar:banana")
        result=self.bot.ask("Remove eggs from this recipe.")
        self.assertEqual(result["status"],"supported_variant")
        variant=result["candidates"][0]
        self.assertEqual(variant["evidence_id"],"epi:banana")
        self.assertEqual(variant["updated_ingredients"],self.store.recipe("epi:banana")["ingredients"])
        self.assertTrue(variant["revised_instructions"])
        self.assertFalse(violations(variant["updated_ingredients"],["egg"]))

    def test_weak_evidence_abstains(self):
        self.bot.ask("/show epi:eggwhite")
        result=self.bot.ask("Remove eggs from this recipe.")
        self.assertEqual(result["status"],"unsupported")
        self.assertEqual(result["candidates"],[])

    def test_unknown_and_invalid_json_are_atomic(self):
        self.bot.ask("/search penne")
        before=self.bot.state.filters()
        self.assertEqual(self.bot.ask('/json {"action":"search","query":"banana","limit":-1}')["kind"],"error")
        self.assertEqual(self.bot.state.filters(),before)
        self.assertEqual(self.bot.ask("Think of something nice")["kind"],"unknown")
        self.assertEqual(self.bot.state.filters(),before)

    def test_unknown_attributes_refused(self):
        self.assertEqual(self.bot.ask("How many calories does it have?")["kind"],"unavailable")

    def test_selected_recipe_facts_are_not_dataset_counts(self):
        self.bot.ask("/show ar:p1")
        fact=self.bot.ask("Does this recipe contain garlic?")
        self.assertEqual(fact["id"],"ar:p1")
        self.assertEqual(fact["value"],["1 clove garlic"])
        self.assertEqual(self.bot.ask("How many ingredients does this recipe have?")["value"],3)
        self.assertEqual(self.bot.ask("How many steps does it have?")["value"],2)

    def test_restrictions_removed_only_explicitly(self):
        self.bot.ask("/exclude egg")
        self.bot.ask("/search banana bread")
        self.assertIn("egg",self.bot.state.exclude)
        self.bot.ask("/allow egg")
        self.assertNotIn("egg",self.bot.state.exclude)

    def test_step_rule(self):
        self.assertEqual(len(steps("Mix.\nBake. Cool.")),2)
        self.assertEqual(len(steps("Mix. Bake. Cool.")),3)
        self.assertEqual(len(steps("")),0)

    def test_plant_products_not_dairy_but_other_dairy_still_caught(self):
        self.assertFalse(violations(["1 cup coconut milk","cream of tartar"],["dairy"]))
        self.assertTrue(violations(["coconut milk and butter"],["dairy"]))
        self.assertTrue(violations(["1 cup Parmesan"],["dairy"]))


if __name__=="__main__": unittest.main()
