## 2025-05-22 - [Cache API Clients for Connection Reuse]
**Learning:** Recreating OpenAI/HTTP clients for every request (or session) prevents connection pooling (Keep-Alive), leading to increased latency due to repeated TCP/TLS handshakes. In a desktop voice app, this latency is critical.
**Action:** Always check if API clients can be reused. If they are stateless or configuration-based, cache them and only recreate on config change.
