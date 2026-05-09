"""Built-in benchmark corpus — no external downloads required."""
from typing import List, Dict, Any

# Each memory: {content, category, project, tags}
MEMORIES: List[Dict[str, Any]] = [
    # Infrastructure / DevOps
    {"content": "Redis requires network_mode: host in Docker Compose or connections silently fail", "category": "learning", "project": "infra", "tags": "redis,docker,networking"},
    {"content": "PostgreSQL max_connections defaults to 100; exceeded connections cause 'sorry too many clients' error", "category": "error", "project": "infra", "tags": "postgres,connections,database"},
    {"content": "Nginx returns 502 Bad Gateway when upstream Node.js process crashes or is unreachable", "category": "error", "project": "infra", "tags": "nginx,node,502"},
    {"content": "PM2 ecosystem.config.js max_restarts defaults to 15; after that PM2 stops restarting the process", "category": "learning", "project": "infra", "tags": "pm2,process,restart"},
    {"content": "SSL certificate renewal with Certbot requires port 80 to be open even for HTTPS-only sites", "category": "learning", "project": "infra", "tags": "ssl,certbot,letsencrypt"},
    {"content": "Docker build cache invalidates when any layer changes; pin base image versions to avoid surprise rebuilds", "category": "learning", "project": "infra", "tags": "docker,cache,build"},
    # WhatsApp / Baileys
    {"content": "Baileys rate limit: 20 messages per minute to new contacts, 60 to known contacts", "category": "learning", "project": "baileys", "tags": "whatsapp,rate-limit,baileys"},
    {"content": "WhatsApp bans numbers sending >200 messages/day to strangers within first 7 days of registration", "category": "learning", "project": "baileys", "tags": "whatsapp,ban,warmup"},
    {"content": "Baileys LID/PN race condition causes Bad MAC errors when crypto session established under wrong JID form", "category": "error", "project": "baileys", "tags": "baileys,bad-mac,lid,jid"},
    {"content": "WhatsApp 463 error means reachout timelock active — bot is blocked from contacting strangers for up to 24h", "category": "learning", "project": "baileys", "tags": "whatsapp,463,timelock"},
    {"content": "Deaf session bug: WebSocket stays open, keepAlive pings succeed, but messages.upsert stops firing due to messageMutex deadlock", "category": "error", "project": "baileys", "tags": "baileys,deaf-session,websocket,mutex"},
    # Python / AI
    {"content": "SQLite FTS5 MATCH operator uses BM25 ranking by default; use rank column for ordering", "category": "learning", "project": "ai-iq", "tags": "sqlite,fts5,search,bm25"},
    {"content": "all-MiniLM-L6-v2 produces 384-dimensional embeddings; cosine distance 0=identical 2=opposite", "category": "learning", "project": "ai-iq", "tags": "embeddings,minilm,vector-search"},
    {"content": "Reciprocal Rank Fusion formula: score += 1/(k+rank+1) where k=60 prevents top-ranked from dominating", "category": "learning", "project": "ai-iq", "tags": "rrf,search,ranking"},
    {"content": "ONNX Runtime CPU inference for MiniLM: ~8ms per embedding on modern hardware", "category": "learning", "project": "ai-iq", "tags": "onnx,inference,performance"},
    # Node.js / React
    {"content": "React 19 use() hook suspends on promise; wrap in Suspense or use RSC for data fetching", "category": "learning", "project": "frontend", "tags": "react,suspense,hooks"},
    {"content": "Tailwind CSS 4 uses CSS variables for theme; @theme directive replaces tailwind.config.js", "category": "learning", "project": "frontend", "tags": "tailwind,css,theme"},
    {"content": "Vite 8 deprecates CommonJS output; all plugins must be ESM-compatible", "category": "learning", "project": "frontend", "tags": "vite,esm,build"},
    {"content": "Express rate-limiter must be applied before body-parser or OPTIONS preflight bypasses limits", "category": "learning", "project": "backend", "tags": "express,rate-limit,cors"},
    {"content": "Node.js EventEmitter memory leak warning fires after 11 listeners; use setMaxListeners() or cleanup properly", "category": "error", "project": "backend", "tags": "node,eventemitter,memory-leak"},
    # Database
    {"content": "SQLite WAL mode allows concurrent readers with a single writer; default journal mode blocks all readers during write", "category": "learning", "project": "infra", "tags": "sqlite,wal,concurrency"},
    {"content": "PostgreSQL EXPLAIN ANALYZE shows actual row counts vs estimates; large differences indicate stale statistics", "category": "learning", "project": "infra", "tags": "postgres,explain,query-plan"},
    {"content": "Redis KEYS command blocks the server; use SCAN with cursor for production key iteration", "category": "learning", "project": "infra", "tags": "redis,keys,scan,performance"},
    # Security / GDPR
    {"content": "GDPR Article 17 right to erasure: must be fulfilled within 30 days; audit trail must survive deletion", "category": "learning", "project": "compliance", "tags": "gdpr,erasure,privacy"},
    {"content": "EU AI Act fully applies August 2026; high-risk AI systems need 10-year audit logs and human oversight", "category": "learning", "project": "compliance", "tags": "eu-ai-act,compliance,audit"},
    # Payments
    {"content": "Stripe requires idempotency keys for all POST requests to prevent duplicate charges on network retry", "category": "learning", "project": "payments", "tags": "stripe,idempotency,payments"},
    {"content": "PayFast sandbox and production use different merchant IDs; swapping keys causes signature validation failure", "category": "error", "project": "payments", "tags": "payfast,sandbox,signature"},
    # General programming
    {"content": "Circular imports in Python: use lazy imports inside functions or restructure into a common module", "category": "learning", "project": "python", "tags": "python,imports,circular"},
    {"content": "Git rebase -i allows squashing commits; use fixup instead of squash to discard commit messages automatically", "category": "learning", "project": "git", "tags": "git,rebase,squash"},
    {"content": "JWT tokens signed with RS256 require public key for verification; HS256 uses shared secret — never use HS256 in distributed systems", "category": "learning", "project": "security", "tags": "jwt,rs256,security"},
    {"content": "WebSocket connections require sticky sessions in load balancers; without it connections randomly drop on redeploy", "category": "error", "project": "infra", "tags": "websocket,load-balancer,sticky-sessions"},
    {"content": "object-cover crops images to fill container; object-contain preserves aspect ratio with letterboxing", "category": "learning", "project": "frontend", "tags": "css,images,object-fit"},
    {"content": "Personalized PageRank seeds from top search results to find 2-3 hop related memories via graph traversal", "category": "learning", "project": "ai-iq", "tags": "ppr,graph,search"},
    {"content": "SQLite vector search with sqlite-vec uses k parameter in WHERE clause; cannot use LIMIT alone", "category": "learning", "project": "ai-iq", "tags": "sqlite-vec,vector,k-nearest"},
    {"content": "Contrastive self-supervised learning trains encoders without labels; SimCSE uses dropout as positive augmentation", "category": "learning", "project": "ai-iq", "tags": "ssl,simcse,embeddings,contrastive"},
]

# Each query: {query, relevant_indices (0-based into MEMORIES), query_type}
# query_type: 'keyword' | 'semantic' | 'causal'
QUERIES: List[Dict[str, Any]] = [
    # Keyword queries (exact terms present in memories)
    {"query": "Redis Docker networking", "relevant": [0, 22], "type": "keyword"},
    {"query": "nginx 502 upstream", "relevant": [2], "type": "keyword"},
    {"query": "PM2 restart limit", "relevant": [3], "type": "keyword"},
    {"query": "WhatsApp ban warmup", "relevant": [7], "type": "keyword"},
    {"query": "Baileys 463 timelock", "relevant": [9], "type": "keyword"},
    {"query": "GDPR erasure audit trail", "relevant": [23, 24], "type": "keyword"},
    {"query": "Stripe idempotency duplicate charges", "relevant": [25], "type": "keyword"},
    # Semantic queries (paraphrase, no exact terms)
    {"query": "database too many connections", "relevant": [1], "type": "semantic"},
    {"query": "SSL certificate renewal process", "relevant": [4], "type": "semantic"},
    {"query": "WhatsApp messages stop arriving but connection seems fine", "relevant": [10], "type": "semantic"},
    {"query": "combining keyword and vector search scores", "relevant": [13], "type": "semantic"},
    {"query": "React data loading pattern", "relevant": [15], "type": "semantic"},
    {"query": "concurrent database reads and writes", "relevant": [20], "type": "semantic"},
    {"query": "image display cropping layout", "relevant": [31], "type": "semantic"},
    {"query": "graph-based memory ranking", "relevant": [32], "type": "semantic"},
    # Causal queries (why/caused/led to patterns)
    {"query": "why does redis fail to connect in docker", "relevant": [0], "type": "causal"},
    {"query": "what caused the Bad MAC error in Baileys", "relevant": [8], "type": "causal"},
    {"query": "why did the Node.js process stop restarting", "relevant": [3], "type": "causal"},
    {"query": "what led to the WebSocket dropping messages", "relevant": [10], "type": "causal"},
    {"query": "why does PayFast signature validation fail", "relevant": [26], "type": "causal"},
    {"query": "what causes the GDPR erasure obligation", "relevant": [23, 24], "type": "causal"},
    {"query": "why use object-contain instead of object-cover", "relevant": [31], "type": "causal"},
    {"query": "what causes EventEmitter memory leak warning", "relevant": [19], "type": "causal"},
    {"query": "why do WebSocket connections drop on redeploy", "relevant": [30], "type": "causal"},
    {"query": "what makes JWT HS256 unsafe in distributed systems", "relevant": [29], "type": "causal"},
]
