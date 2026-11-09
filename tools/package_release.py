"""在 web 完成生产构建后，分别打包微信开发者工具项目和网页静态文件。"""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def pack(name, base, files):
    target = ROOT / "发布包" / name
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target.with_suffix(".tmp"), "w", compression=ZIP_DEFLATED) as archive:
        for file in sorted(files):
            archive.write(file, file.relative_to(base).as_posix())
    target.with_suffix(".tmp").replace(target)


def main():
    mini = ROOT / "wechat"
    site = ROOT / "web" / "dist"
    if not all((site / p).is_file() for p in ("index.html", "config.js")) or not list((site/"assets").glob("*.js")):
        raise SystemExit("先在 web 目录运行 pnpm build")
    mini_files = [mini/p for p in ("project.config.json", "package.json", "tsconfig.json", "pnpm-lock.yaml")]
    mini_files.extend(p for p in (mini/"miniprogram").rglob("*") if p.is_file())
    pack("微信小程序.zip", mini, mini_files)
    pack("网页静态站.zip", site, [p for p in site.rglob("*") if p.is_file()])


if __name__ == "__main__":
    main()
