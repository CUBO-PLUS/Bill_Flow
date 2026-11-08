---
name: actualizar-lucid-erd
description: Updates the ERD diagram of the real database (restaurante.db) in Lucid using the Lucid MCP. Use when a table, user, ticket/sale is added or when asked to update/sync the database drawing in Lucid.
---

# Update the ERD in Lucid

Requires the Lucid MCP to be connected (claude.ai → Lucid) with the email/account of the user who has access to Lucid.

1. Read the REAL schema (tables, PK, FK, types) of `restaurante.db`:
   ```bash
   python3 esquema.py
   ```
   It prints JSON `{entities, relationships}` already in the `lucid_create_erd` format.
2. Before using any other Lucid tool, call `get_mcp_resource` with `lucid://skills/readme`.
3. Read `lucid_erd.json` (if it exists) to get the `document_id` and `url` of the previous diagram.
4. Call `lucid_create_erd` with the title `Restaurante DTE - ERD` and that JSON (the MCP does not edit existing
   ERDs: a new document is created with the current schema).
5. Save in `lucid_erd.json`: `{"document_id": "...", "url": "<edit URL>", "actualizado": "<date>"}`.
   The green **Data** button in the app will show the "Open in Lucid" link.
6. If there was a previous document, rename it with `lucid_update_document` to "(obsolete) ..." and tell the user to delete it.
7. Validate with `lucid_export_document_as_PNG` if needed and share the link.

Never include `password_hash` or user data: structure only.
