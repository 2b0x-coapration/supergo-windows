# -*- coding: utf-8 -*-
"""SUPERGO VPN helper: turns vless/vmess/trojan/ss links, subscriptions or raw JSON
into an xray/v2ray config that exposes a local SOCKS5 port, and runs the core."""
import base64, json, os, subprocess, time
from urllib.parse import urlparse, parse_qs, unquote
from urllib.request import urlopen, Request


def _b64(s):
    s = s.strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "ignore")


def _stream(net, sec, p, host=""):
    net = {"h2": "http", "": "tcp"}.get(net, net)
    s = {"network": net, "security": sec or "none"}
    sni = p.get("sni") or p.get("host") or host
    if net == "ws":
        s["wsSettings"] = {"path": p.get("path", "/"), "headers": {"Host": p.get("host", "")}}
    elif net == "grpc":
        s["grpcSettings"] = {"serviceName": p.get("serviceName", "")}
    elif net == "httpupgrade":
        s["httpupgradeSettings"] = {"path": p.get("path", "/"), "host": p.get("host", "")}
    if sec == "tls":
        s["tlsSettings"] = {"serverName": sni, "fingerprint": p.get("fp", "chrome")}
        if p.get("alpn"):
            s["tlsSettings"]["alpn"] = p["alpn"].split(",")
    elif sec == "reality":
        s["realitySettings"] = {"serverName": sni, "fingerprint": p.get("fp", "chrome"),
                                "publicKey": p.get("pbk", ""), "shortId": p.get("sid", ""),
                                "spiderX": p.get("spx", "")}
    return s


def parse_link(link):
    link = link.strip()
    u = urlparse(link)
    sch = u.scheme.lower()
    if sch == "vmess":
        j = json.loads(_b64(link[8:]))
        p = {"host": j.get("host", ""), "path": j.get("path", "/"), "sni": j.get("sni", "")}
        return {"protocol": "vmess", "settings": {"vnext": [{"address": j["add"], "port": int(j["port"]),
                "users": [{"id": j["id"], "alterId": int(j.get("aid", 0) or 0), "security": j.get("scy", "auto")}]}]},
                "streamSettings": _stream(j.get("net", "tcp"), "tls" if j.get("tls") == "tls" else "none", p, j["add"])}
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    if sch == "vless":
        return {"protocol": "vless", "settings": {"vnext": [{"address": u.hostname, "port": u.port,
                "users": [{"id": unquote(u.username), "encryption": q.get("encryption", "none"),
                           "flow": q.get("flow", "")}]}]},
                "streamSettings": _stream(q.get("type", "tcp"), q.get("security", "none"), q, u.hostname)}
    if sch == "trojan":
        return {"protocol": "trojan", "settings": {"servers": [{"address": u.hostname, "port": u.port,
                "password": unquote(u.username)}]},
                "streamSettings": _stream(q.get("type", "tcp"), q.get("security", "tls"), q, u.hostname)}
    if sch == "ss":
        body = link[5:].split("#")[0].split("?")[0]
        if "@" not in body:
            body = _b64(body)
        cred, _, hp = body.rpartition("@")
        if ":" not in cred:
            cred = _b64(cred)
        method, _, pw = cred.partition(":")
        host, _, port = hp.rpartition(":")
        return {"protocol": "shadowsocks", "settings": {"servers": [{"address": host.strip("[]"),
                "port": int(port), "method": method, "password": unquote(pw)}]}}
    raise ValueError("Unsupported link type: " + sch)


def _first_link(text):
    text = text.strip()
    if text.startswith(("http://", "https://")):
        req = Request(text, headers={"User-Agent": "SUPERGO"})
        raw = urlopen(req, timeout=15).read().decode("utf-8", "ignore")
        try:
            raw = _b64(raw)
        except Exception:
            pass
        text = raw
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith(("vless://", "vmess://", "trojan://", "ss://")):
            return line
    raise ValueError("No vless / vmess / trojan / ss link found.")


def build_config(text, port):
    text = text.strip()
    inbound = {"listen": "127.0.0.1", "port": int(port), "protocol": "socks", "settings": {"udp": True, "auth": "noauth"}}
    if text.startswith("{"):
        cfg = json.loads(text)
        cfg["inbounds"] = [inbound]
        return cfg
    out = parse_link(_first_link(text))
    out["tag"] = "proxy"
    return {"log": {"loglevel": "none"}, "inbounds": [inbound],
            "outbounds": [out, {"protocol": "freedom", "tag": "direct"}]}


def find_core(dirs):
    for d in dirs:
        for n in ("xray.exe", "v2ray.exe"):
            p = os.path.join(d, n)
            if os.path.isfile(p):
                return p
    return None


def start(text, port, dirs, datadir):
    core = find_core(dirs)
    if not core:
        raise RuntimeError("xray.exe (or v2ray.exe) not found next to SUPERGO.exe")
    cfg = build_config(text, port)
    path = os.path.join(datadir, "core-config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    args = [core, "run", "-c", path] if os.path.basename(core).lower().startswith("xray") else [core, "-config", path]
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    p = subprocess.Popen(args, cwd=os.path.dirname(core), creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    if p.poll() is not None:
        raise RuntimeError("VPN core exited immediately - check your link/config")
    return p


def stop(p):
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(3)
        except Exception:
            p.kill()
