---
name: actualizar-lucid-erd
description: Actualiza el diagrama ERD de la base de datos real (restaurante.db) en Lucid usando el MCP de Lucid. Usar cuando se agregue una tabla, usuario, ticket/venta o se pida actualizar/sincronizar el dibujo de la base de datos en Lucid.
---

# Actualizar el ERD en Lucid

Requiere el MCP de Lucid conectado (claude.ai → Lucid) con la cuenta/email del usuario con acceso a Lucid.

1. Lee el esquema REAL (tablas, PK, FK, tipos) de `restaurante.db`:
   ```bash
   python3 esquema.py
   ```
   Imprime JSON `{entities, relationships}` ya en el formato de `lucid_create_erd`.
2. Antes de usar otra herramienta de Lucid, llama `get_mcp_resource` con `lucid://skills/readme`.
3. Lee `lucid_erd.json` (si existe) para ver el `document_id` y `url` del diagrama anterior.
4. Llama `lucid_create_erd` con título `Restaurante DTE - ERD` y ese JSON (el MCP no edita ERDs
   existentes: se crea un documento nuevo con el esquema actual).
5. Guarda en `lucid_erd.json`: `{"document_id": "...", "url": "<edit URL>", "actualizado": "<fecha>"}`.
   El botón verde **Data** de la app mostrará el enlace "Abrir en Lucid".
6. Si había un documento anterior, renómbralo con `lucid_update_document` a "(obsoleto) ..." y dile al usuario que lo borre.
7. Valida con `lucid_export_document_as_PNG` si hace falta y comparte el enlace.

Nunca incluyas `password_hash` ni datos de usuarios: solo estructura.
