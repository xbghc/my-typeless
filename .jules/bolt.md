## 2025-04-09 - Adding Multiple LLM/STT Providers
**Learning:** Adding multi-provider support required complex UI restructuring (combining dropdown lists, active state syncing, array modification in javascript). Data migration logic on the backend (`config.py`) must gracefully handle legacy single-provider JSON configs without crashing.
**Action:** When refactoring configuration to support collections of items instead of single scalar objects, always include backward-compatible `load()` parsing logic for users running on older file schemas.
