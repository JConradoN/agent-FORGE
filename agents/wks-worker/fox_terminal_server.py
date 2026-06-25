#!/usr/bin/env python3
"""
Fox Terminal Server — servidor de terminal compatível com Open WebUI
Porta 9900, backend PowerShell, autenticação Bearer via primeira mensagem WS.
"""
import asyncio, json, uuid, datetime, os, stat, mimetypes, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fox-terminal")
from fastapi import FastAPI, WebSocket, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect
import uvicorn

API_KEY = os.environ.get("TERMINAL_API_KEY", "foxwks-terminal-2026")
WORKSPACE = Path(os.environ.get("TERMINAL_WORKSPACE", "D:\\"))

app = FastAPI(title="Fox Terminal Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict = {}


def _check_auth(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/api/config")
async def get_config(request: Request):
    _check_auth(request)
    return {"version": "1.0", "type": "terminal", "shell": "powershell"}


@app.get("/api/terminals")
async def list_terminals(request: Request):
    _check_auth(request)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    return [
        {"id": sid, "name": "", "last_activity": now, "env_variables": {}, "connections": 1}
        for sid, info in sessions.items()
        if info.get("proc") and info["proc"].returncode is None
    ]


@app.post("/api/terminals")
async def create_terminal(request: Request):
    _check_auth(request)
    sid = str(uuid.uuid4())
    sessions[sid] = {"proc": None}
    return {
        "id": sid,
        "name": "",
        "last_activity": datetime.datetime.utcnow().isoformat() + "Z",
        "env_variables": {},
        "connections": 0,
    }


@app.delete("/api/terminals/{session_id}")
async def delete_terminal(session_id: str, request: Request):
    _check_auth(request)
    info = sessions.pop(session_id, None)
    if info and info.get("proc"):
        try:
            info["proc"].terminate()
        except Exception:
            pass
    return Response(status_code=204)


@app.websocket("/api/terminals/{session_id}")
async def ws_terminal(ws: WebSocket, session_id: str):
    await ws.accept()

    # Primeira mensagem: autenticação enviada pelo proxy Open WebUI
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=10.0)
        msg = json.loads(raw)
        if msg.get("type") != "auth" or msg.get("token") != API_KEY:
            await ws.close(code=4001, reason="Unauthorized")
            return
    except Exception:
        await ws.close(code=4001, reason="Auth failed")
        return

    # Inicia PowerShell partindo de D:\
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell.exe", "-NoProfile", "-NoLogo", "-NonInteractive", "-Command", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        # navega para D:\ ao iniciar
        proc.stdin.write(b"cd D:\\; function prompt { \"PS D:\\> \" }\n")
        await proc.stdin.drain()
    except Exception as e:
        await ws.send_text(f"[ERRO] powershell nao iniciou: {e}\r\n")
        await ws.close()
        return

    sessions[session_id] = {"proc": proc}

    async def read_stdout():
        while True:
            data = await proc.stdout.read(4096)
            if not data:
                break
            await ws.send_text(data.decode("utf-8", errors="replace"))

    async def write_stdin():
        while True:
            try:
                raw = await ws.receive_text()
                # aceita tanto texto puro quanto ["stdin","..."] do Jupyter
                try:
                    msg = json.loads(raw)
                    if isinstance(msg, list) and msg[0] == "stdin":
                        raw = msg[1]
                    elif isinstance(msg, dict):
                        raw = msg.get("text", "")
                except (json.JSONDecodeError, Exception):
                    pass  # raw já é texto puro
                if raw:
                    proc.stdin.write(raw.encode("utf-8"))
                    await proc.stdin.drain()
            except (WebSocketDisconnect, Exception):
                break

    tasks = [
        asyncio.create_task(read_stdout()),
        asyncio.create_task(write_stdin()),
    ]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass

    try:
        proc.terminate()
    except Exception:
        pass
    sessions.pop(session_id, None)
    try:
        await ws.close()
    except Exception:
        pass


_cwd: Path = WORKSPACE


def _resolve_path(rel: str) -> Path:
    """Resolve caminho relativo ao workspace, bloqueando traversal."""
    rel = rel.strip("/").replace("/", os.sep)
    resolved = (WORKSPACE / rel).resolve() if rel else WORKSPACE.resolve()
    if not str(resolved).upper().startswith(str(WORKSPACE).upper()):
        raise HTTPException(status_code=403, detail="Path fora do workspace")
    return resolved


def _contents_entry(p: Path, include_content: bool = False) -> dict:
    now = datetime.datetime.utcnow().isoformat() + "Z"
    try:
        rel = str(p.relative_to(WORKSPACE)).replace(os.sep, "/")
    except ValueError:
        rel = ""
    if rel == ".":
        rel = ""
    if p.is_dir():
        entry: dict = {
            "name": p.name,
            "path": rel,
            "type": "directory",
            "last_modified": now,
            "created": now,
            "content": None,
            "format": None,
            "mimetype": None,
            "size": None,
            "writable": True,
        }
        if include_content:
            entry["content"] = [_contents_entry(child) for child in sorted(p.iterdir())]
            entry["format"] = "json"
        return entry
    else:
        mime = mimetypes.guess_type(p.name)[0] or "text/plain"
        size = p.stat().st_size
        entry = {
            "name": p.name,
            "path": rel,
            "type": "file",
            "last_modified": now,
            "created": now,
            "content": None,
            "format": None,
            "mimetype": mime,
            "size": size,
            "writable": True,
        }
        if include_content:
            try:
                entry["content"] = p.read_text(encoding="utf-8", errors="replace")
                entry["format"] = "text"
            except Exception:
                entry["content"] = ""
                entry["format"] = "text"
        return entry


@app.get("/api/contents")
@app.get("/api/contents/{path:path}")
async def get_contents(request: Request, path: str = ""):
    _check_auth(request)
    target = _resolve_path(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return _contents_entry(target, include_content=True)


@app.put("/api/contents/{path:path}")
async def put_contents(path: str, request: Request):
    _check_auth(request)
    target = _resolve_path(path)
    body = await request.json()
    if body.get("type") == "directory":
        target.mkdir(parents=True, exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        content = body.get("content", "")
        target.write_text(content, encoding="utf-8")
    return _contents_entry(target)


@app.delete("/api/contents/{path:path}")
async def delete_contents(path: str, request: Request):
    _check_auth(request)
    target = _resolve_path(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Not found")
    import shutil
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return Response(status_code=204)


def _unix_to_win(unix_path: str) -> Path:
    """Converte path virtual unix (/subdir) para path Windows real (D:\\subdir)."""
    rel = unix_path.strip("/")
    if not rel:
        return WORKSPACE
    resolved = (WORKSPACE / rel.replace("/", os.sep)).resolve()
    if not str(resolved).upper().startswith(str(WORKSPACE.resolve()).upper()):
        raise HTTPException(status_code=403, detail="Path fora do workspace")
    return resolved


def _win_to_unix(win_path: Path) -> str:
    """Converte path Windows real para path virtual unix."""
    try:
        rel = str(win_path.relative_to(WORKSPACE)).replace(os.sep, "/")
        return "/" + rel if rel != "." else "/"
    except ValueError:
        return "/"


def _list_dir(directory: str) -> list:
    target = _unix_to_win(directory)
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")
    entries = []
    for p in sorted(target.iterdir()):
        entries.append({
            "name": p.name,
            "path": _win_to_unix(p),
            "type": "directory" if p.is_dir() else "file",
            "size": p.stat().st_size if p.is_file() else None,
            "modified": datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
        })
    return entries


@app.get("/files/cwd")
async def get_cwd(request: Request):
    _check_auth(request)
    return {"cwd": _win_to_unix(_cwd)}


@app.post("/files/cwd")
async def set_cwd(request: Request):
    global _cwd
    _check_auth(request)
    body = await request.json()
    log.info("POST /files/cwd body: %s", body)
    directory = body.get("directory", "/")
    new_path = _unix_to_win(directory)
    if not new_path.is_dir():
        raise HTTPException(status_code=400, detail="Not a directory")
    _cwd = new_path
    return {"cwd": _win_to_unix(_cwd)}


@app.post("/files/mkdir")
async def make_dir(request: Request):
    _check_auth(request)
    body = await request.json()
    log.info("POST /files/mkdir body: %s", body)
    path = body.get("path", "")
    target = _unix_to_win(path)
    target.mkdir(parents=True, exist_ok=True)
    return {"path": _win_to_unix(target), "type": "directory"}


@app.get("/files/list")
async def list_files(request: Request, directory: str = "/"):
    _check_auth(request)
    return {"entries": _list_dir(directory)}


@app.get("/files/read")
async def read_file_api(request: Request, path: str):
    _check_auth(request)
    target = _unix_to_win(path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return {"content": target.read_text(encoding="utf-8", errors="replace"), "path": _win_to_unix(target)}


@app.post("/files/write")
async def write_file_api(request: Request):
    _check_auth(request)
    body = await request.json()
    path = body.get("path", "")
    content = body.get("content", "")
    target = _unix_to_win(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": _win_to_unix(target), "size": len(content)}


@app.get("/ports")
async def get_ports(request: Request):
    _check_auth(request)
    try:
        result = await asyncio.create_subprocess_exec(
            "powershell.exe", "-NoProfile", "-Command",
            "Get-NetTCPConnection -State Listen | Select-Object LocalPort,OwningProcess | "
            "Sort-Object LocalPort | ForEach-Object { "
            "$p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; "
            "[PSCustomObject]@{port=$_.LocalPort; pid=$_.OwningProcess; process=if($p){$p.Name}else{'unknown'}} "
            "} | ConvertTo-Json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(result.communicate(), timeout=10)
        raw = stdout.decode("utf-8", errors="replace").strip()
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            return {"ports": data}
    except Exception:
        pass
    return {"ports": []}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9900, log_level="info")
