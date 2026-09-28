"""Content-Disposition 文件名面板。

跑法（副本内，别在种子仓跑）：
    cd /tmp/b138-xxx && .venv/bin/python <本文件>
首行打印被测 starlette 的 __file__，坐实测的是副本里的代码。
"""

import json

import starlette
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

print("TARGET starlette.__file__ =", starlette.__file__, "| version =", starlette.__version__)

TMP = "/tmp/b138-panel-f.txt"
results = []


async def upload(request: Request):
    form = await request.form()
    out = []
    for _, v in form.items():
        out.append({"kind": type(v).__name__, "filename": getattr(v, "filename", None)})
    return PlainTextResponse(json.dumps(out, ensure_ascii=False))


async def download(request: Request):
    with open(TMP, "wb") as fh:
        fh.write(b"BODY")
    return FileResponse(TMP, filename=request.query_params["n"])


app = Starlette(routes=[Route("/up", upload, methods=["POST"]), Route("/down", download)])
client = TestClient(app)

BOUNDARY = b"----Z\r\n"


def raw_part(disposition_bytes: bytes, extra_ct: str = "", part_ct: bytes = b"Content-Type: text/plain\r\n"):
    """自己拼 multipart 体，绕开 TestClient 对文件名的再加工。"""
    body = BOUNDARY + b"Content-Disposition: form-data; " + disposition_bytes + b"\r\n" + part_ct + b"\r\nAAA\r\n"
    body += b"----Z--\r\n"
    r = client.post("/up", content=body, headers={"content-type": "multipart/form-data; boundary=--Z" + extra_ct})
    if r.status_code != 200:
        return {"error": "HTTP%s %s" % (r.status_code, r.text[:70])}
    return json.loads(r.text)[0]


def cd(raw_disposition: str) -> bytes:
    return raw_disposition.encode("latin-1")


def upload_name(raw_disposition: str, extra_ct: str = ""):
    got = raw_part(cd(raw_disposition), extra_ct)
    return got.get("filename", got.get("error"))


def upload_kind(raw_disposition: str):
    got = raw_part(cd(raw_disposition))
    return got.get("kind", got.get("error"))


def emit_and_read_back(name: str):
    r = client.get("/down", params={"n": name})
    hdr = r.headers.get("content-disposition", "")
    tail = hdr.split("; ", 1)[1] if "; " in hdr else hdr
    return hdr, upload_name('name="f"; ' + tail)


def cell(label, fn, want):
    try:
        got = fn()
    except BaseException as exc:  # 起点里读不到的形状也要让整块面板跑完
        got = "RAISED:" + type(exc).__name__ + ":" + str(exc)[:60]
    ok = got == want
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + label + " | got=" + repr(got) + " want=" + repr(want))
    return got


STAR = "filename*=UTF-8''%E4%B8%AD.txt"

cell("C1 上传只给 filename*=UTF-8''… 时读到的文件名", lambda: upload_name('name="f"; ' + STAR), "中.txt")
cell(
    "C2 上传同时给 filename 与 filename* 时读到的文件名",
    lambda: upload_name('name="f"; filename="fallback.txt"; ' + STAR),
    "中.txt",
)
cell(
    "C3 上传 filename*=iso-8859-1'fr'… 时读到的文件名",
    lambda: upload_name("name=\"f\"; filename*=iso-8859-1'fr'caf%E9.txt"),
    "café.txt",
)
cell('C4 上传 filename="a/b.txt" 时读到的文件名', lambda: upload_name('name="f"; filename="a/b.txt"'), "b.txt")
cell('C5 上传 filename="plain.txt" 时读到的文件名', lambda: upload_name('name="f"; filename="plain.txt"'), "plain.txt")
cell(
    'C6 charset=iso-8859-1 的上传体里 filename="caf\\xe9.txt" 读到的文件名',
    lambda: upload_name('name="f"; filename="caf\xe9.txt"', "; charset=iso-8859-1"),
    "café.txt",
)
cell("C7 上传只给 filename* 的那一段在 form 里的类型", lambda: upload_kind('name="f"; ' + STAR), "UploadFile")
cell(
    "C8 上传 filename* 声明的字符集认不出、同段还有 filename 时读到的文件名",
    lambda: upload_name("name=\"f\"; filename*=unknown-cs''bad%25.txt; filename=\"ok.txt\""),
    "ok.txt",
)
cell("C9 自己发出的非 ASCII 文件名读回原样", lambda: emit_and_read_back("你好.txt")[1], "你好.txt")
print("     C9 emitted: " + repr(emit_and_read_back("你好.txt")[0]))
cell("C10 自己发出的含 '/' 的文件名读回原样", lambda: emit_and_read_back("a/b.txt")[1], "a/b.txt")
print("     C10 emitted: " + repr(emit_and_read_back("a/b.txt")[0]))
cell(
    "C11 非 ASCII 文件名发出的头字面",
    lambda: client.get("/down", params={"n": "你好.txt"}).headers.get("content-disposition"),
    "attachment; filename*=utf-8''%E4%BD%A0%E5%A5%BD.txt",
)
cell(
    "C12 纯 ASCII 文件名发出的头字面",
    lambda: client.get("/down", params={"n": "example.png"}).headers.get("content-disposition"),
    'attachment; filename="example.png"',
)

print("PANEL %d/%d" % (sum(results), len(results)))
