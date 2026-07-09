from app.config import Settings


class IntegrationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def zmq_status(self) -> dict[str, object]:
        rawblock = self.settings.bitcoin_zmq_rawblock.strip()
        rawtx = self.settings.bitcoin_zmq_rawtx.strip()
        configured = bool(rawblock or rawtx)

        return {
            "configured": configured,
            "rawblock_endpoint": rawblock or None,
            "rawtx_endpoint": rawtx or None,
            "sse_endpoint": f"{self.settings.api_prefix}/live/node",
            "zmq_listener_available": False,
            "recommended_bitcoin_conf": [
                "zmqpubrawblock=tcp://127.0.0.1:28332",
                "zmqpubrawtx=tcp://127.0.0.1:28333",
            ],
            "warnings": []
            if configured
            else [
                "ZMQ endpoints are not configured in BitScope. The live monitor still works through polling-backed Server-Sent Events.",
                "Set BITCOIN_ZMQ_RAWBLOCK and BITCOIN_ZMQ_RAWTX after enabling matching zmqpubrawblock and zmqpubrawtx values in bitcoin.conf.",
            ],
            "cli_commands": [
                "bitcoin-cli getzmqnotifications",
                "bitcoin-cli getblockchaininfo",
            ],
            "rpc_methods": ["getzmqnotifications", "getblockchaininfo"],
            "concepts": ["ZMQ", "Server-Sent Events", "Raw block", "Raw transaction", "Event-driven integration"],
            "explanation": (
                "Bitcoin Core can publish raw block and raw transaction notifications over ZMQ. BitScope's current live "
                "monitor uses reliable polling-backed SSE, while this status endpoint shows whether ZMQ endpoints are configured "
                "for an event-driven listener extension."
            ),
            "raw": {
                "settings": {
                    "bitcoin_zmq_rawblock_configured": bool(rawblock),
                    "bitcoin_zmq_rawtx_configured": bool(rawtx),
                }
            },
        }

    def rpc_examples(self) -> dict[str, object]:
        examples = [
            {
                "language": "curl",
                "title": "Raw JSON-RPC with basic auth",
                "description": "The smallest direct request shape. Replace placeholders with local credentials from bitcoin.conf.",
                "code": (
                    "curl --user <rpcuser>:<rpcpassword> --data-binary "
                    "'{\"jsonrpc\":\"1.0\",\"id\":\"bitscope\",\"method\":\"getblockchaininfo\",\"params\":[]}' "
                    "-H 'content-type: text/plain;' http://127.0.0.1:18443/"
                ),
            },
            {
                "language": "Python",
                "title": "Python requests session",
                "description": "Use a single session and keep credentials server-side.",
                "code": (
                    "import requests\n\n"
                    "url = \"http://127.0.0.1:18443/\"\n"
                    "auth = (\"<rpcuser>\", \"<rpcpassword>\")\n"
                    "payload = {\"jsonrpc\": \"1.0\", \"id\": \"bitscope\", \"method\": \"getblockchaininfo\", \"params\": []}\n"
                    "response = requests.post(url, json=payload, auth=auth, timeout=10)\n"
                    "response.raise_for_status()\n"
                    "print(response.json()[\"result\"])\n"
                ),
            },
            {
                "language": "TypeScript",
                "title": "Node fetch with basic auth",
                "description": "Use this only on the server side; never expose RPC credentials to browser code.",
                "code": (
                    "const auth = Buffer.from(\"<rpcuser>:<rpcpassword>\").toString(\"base64\");\n"
                    "const response = await fetch(\"http://127.0.0.1:18443/\", {\n"
                    "  method: \"POST\",\n"
                    "  headers: { \"content-type\": \"application/json\", authorization: `Basic ${auth}` },\n"
                    "  body: JSON.stringify({ jsonrpc: \"1.0\", id: \"bitscope\", method: \"getblockchaininfo\", params: [] })\n"
                    "});\n"
                    "const body = await response.json();\n"
                    "console.log(body.result);\n"
                ),
            },
            {
                "language": "Go",
                "title": "Go net/http client",
                "description": "Create explicit requests and set Basic Auth before sending.",
                "code": (
                    "package main\n\n"
                    "import (\n"
                    "  \"bytes\"\n"
                    "  \"fmt\"\n"
                    "  \"net/http\"\n"
                    ")\n\n"
                    "func main() {\n"
                    "  body := []byte(`{\"jsonrpc\":\"1.0\",\"id\":\"bitscope\",\"method\":\"getblockchaininfo\",\"params\":[]}`)\n"
                    "  req, _ := http.NewRequest(\"POST\", \"http://127.0.0.1:18443/\", bytes.NewReader(body))\n"
                    "  req.SetBasicAuth(\"<rpcuser>\", \"<rpcpassword>\")\n"
                    "  req.Header.Set(\"content-type\", \"application/json\")\n"
                    "  resp, err := http.DefaultClient.Do(req)\n"
                    "  if err != nil { panic(err) }\n"
                    "  defer resp.Body.Close()\n"
                    "  fmt.Println(resp.Status)\n"
                    "}\n"
                ),
            },
            {
                "language": "Rust",
                "title": "Rust reqwest blocking client",
                "description": "A compact example for command-line tools and tests.",
                "code": (
                    "use reqwest::blocking::Client;\n"
                    "use serde_json::json;\n\n"
                    "fn main() -> Result<(), Box<dyn std::error::Error>> {\n"
                    "    let client = Client::new();\n"
                    "    let response = client\n"
                    "        .post(\"http://127.0.0.1:18443/\")\n"
                    "        .basic_auth(\"<rpcuser>\", Some(\"<rpcpassword>\"))\n"
                    "        .json(&json!({\"jsonrpc\":\"1.0\",\"id\":\"bitscope\",\"method\":\"getblockchaininfo\",\"params\":[]}))\n"
                    "        .send()?;\n"
                    "    println!(\"{}\", response.text()?);\n"
                    "    Ok(())\n"
                    "}\n"
                ),
            },
        ]

        return {
            "rpc_url": self.settings.rpc_url,
            "wallet_rpc_path": f"{self.settings.rpc_url}/wallet/<wallet-name>",
            "examples": examples,
            "zmq_conf": [
                "zmqpubrawblock=tcp://127.0.0.1:28332",
                "zmqpubrawtx=tcp://127.0.0.1:28333",
            ],
            "cli_commands": ["bitcoin-cli getblockchaininfo", "bitcoin-cli -rpcwallet=<wallet-name> getwalletinfo"],
            "rpc_methods": ["getblockchaininfo", "getwalletinfo"],
            "concepts": ["JSON-RPC", "Basic authentication", "Wallet RPC", "Batching", "ZMQ"],
            "explanation": (
                "Bitcoin Core exposes JSON-RPC over HTTP with Basic Auth. Wallet RPC calls use the `/wallet/<wallet-name>` "
                "path, credentials must stay server-side, and ZMQ is a separate publish-subscribe channel for raw node events."
            ),
        }
