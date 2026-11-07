"""Usage: python -m recipebox setup|chat|ask|evaluate."""
import argparse
import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from .store import Store,build,FILES
from .chat import Chatbot,render

ROOT=Path(__file__).resolve().parents[1]
DATA_URL="https://eightportions.com/recipes_raw.zip"


def setup(data_dir):
    data_dir=Path(data_dir)
    raw=data_dir/"raw"
    raw.mkdir(parents=True,exist_ok=True)
    if not all((raw/f).exists() for f in FILES.values()):
        archive=data_dir/"recipes_raw.zip"
        print("Downloading all three source files from "+DATA_URL,flush=True)
        request=urllib.request.Request(DATA_URL,headers={"User-Agent":"RecipeBoxAssignment/1.0"})
        with urllib.request.urlopen(request,timeout=120) as response,archive.open("wb") as out:
            while chunk:=response.read(1024*1024): out.write(chunk)
        with zipfile.ZipFile(archive) as z:
            # Extract named files only, never arbitrary archive paths.
            for name in list(FILES.values())+["LICENSE"]:
                if name in z.namelist(): (raw/name).write_bytes(z.read(name))
    manifest=build(raw,data_dir/"recipes.sqlite3")
    manifest["archive_url"]=DATA_URL
    if (data_dir/"recipes_raw.zip").exists(): manifest["archive_sha256"]=hashlib.file_digest((data_dir/"recipes_raw.zip").open("rb"),"sha256").hexdigest()
    (data_dir/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest,indent=2))


def main():
    parser=argparse.ArgumentParser(description="Grounded Recipe Box chatbot; Python 3.11+, SQLite FTS5; no API key.")
    parser.add_argument("command",choices=["setup","chat","ask","evaluate"])
    parser.add_argument("message",nargs="?")
    parser.add_argument("--data-dir",type=Path,default=ROOT/"data")
    parser.add_argument("--json",action="store_true",help="Machine-readable response")
    args=parser.parse_args()
    if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    if args.command=="setup": setup(args.data_dir); return
    if args.command=="evaluate":
        from .evaluate import run
        run(args.data_dir/"recipes.sqlite3",ROOT/"docs")
        return
    store=Store(args.data_dir/"recipes.sqlite3")
    bot=Chatbot(store)
    try:
        if args.command=="ask":
            if not args.message: parser.error("ask requires a message")
            response=bot.ask(args.message)
            print(json.dumps(response,ensure_ascii=False,indent=2) if args.json else render(response))
        else:
            print("Recipe Box | grounded local assistant\nType /help for examples; /quit to exit.")
            while True:
                try: message=input("\nYou> ")
                except (EOFError,KeyboardInterrupt): break
                response=bot.ask(message)
                print("\nBot> "+(json.dumps(response,ensure_ascii=False,indent=2) if args.json else render(response)))
                if response["kind"]=="quit": break
    finally: store.close()


if __name__=="__main__": main()
