# Source provenance and learning record

Reviewed on 2026-11-18. MFIERP is authoritative for integration decisions; upstream projects are authoritative for their respective APIs/framework behavior. Reviewed branch heads are evidence, not deployment promises.

| Source | Reviewed revision | Applied learning |
| --- | --- | --- |
| [MFIERP](https://github.com/nandahtoon/MFIERP) | `59e71b74972d41d1a9536dcae6a23e50698286dd` | Initial README only; project identity MiFosXinOdoo |
| [Odoo 20](https://github.com/odoo/odoo/tree/c40402fab8c1509f3c68cd9cc5140f7790611d99) | `c40402fab8c1509f3c68cd9cc5140f7790611d99` | 20.0 final, Python >=3.12, PostgreSQL >=16; ir.access model; group privilege model; native view/model conventions |
| [Odoo 19](https://github.com/odoo/odoo/tree/11847c6348e378546fcd1298b8c6e0bd36f3565d) | `11847c6348e378546fcd1298b8c6e0bd36f3565d` | ORM/module baseline and migration comparison; not a claimed runtime target |
| [Mifos X Web App](https://github.com/openMF/web-app/tree/bc59713525c4a95ca21f2c9cf1e03f0f95a1771c) | `bc59713525c4a95ca21f2c9cf1e03f0f95a1771c` | Navigation taxonomy; clients, loans and savings service endpoint patterns; Angular UI is not copied |
| [Apache Fineract](https://github.com/apache/fineract/tree/6a28754c6839fa64f5faf1873f9fcb52bc330fd9) | `6a28754c6839fa64f5faf1873f9fcb52bc330fd9` | Reports, journal, loan and savings REST contracts, command handling and financial authority |
| [Fineract stable documentation](https://fineract.apache.org/docs/stable/) | Reports version 1.16.1 at review time | HTTPS, service authentication, command processing, idempotency and operational model |
| [Owner's Mifos X frontend](https://github.com/nandahtoon/Mifosx-web-app/tree/34c7f278861ef25052f2e00d106d8527f5d270d3) | `34c7f278861ef25052f2e00d106d8527f5d270d3` | 720 literal HTTP calls, 180 action components, fixed command payloads and product accounting mappings; see parity inventory |
| Oracle public OpenAPI | API 1.16.0-SNAPSHOT; canonicalized SHA-256 embedded in catalog | 602 paths, 966 HTTP operations and 1,491 schemas; transformed native contracts with Apache attribution |

Additional framework references:

- [Odoo 20 coding guidelines](https://www.odoo.com/documentation/20.0/contributing/development/coding_guidelines.html), also reviewed from the official documentation repository when the website timed out.
- [Odoo 20 security](https://www.odoo.com/documentation/20.0/developer/reference/backend/security.html), corroborated with `odoo/addons/base/models/ir_access.py` and the project addon security files.
- [Odoo 19 ORM](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html), reviewed from the official documentation repository.

No upstream Angular/Java application source is vendored. The addon is independently authored around the public Fineract API. Source reading is not a certification, full platform mastery or proof of complete feature parity. Runtime verification results are recorded separately in VALIDATION.md.

Extended workspace research also used Odoo 20 `odoo/orm/fields_binary.py` (`BinaryValue`/`BinaryBytes`, rather than legacy base64 bytes), Fineract `fineract-core/.../api/DateParam.java` at the Apache revision above, and Python's standard-library HMAC API for constant-time secret-binding verification. The OpenAPI metadata is a licensed transformed artifact; Angular/Java implementation files remain an ignored local research cache.

## Owner's deployment and governance sources

At the owner's follow-up direction, the connected GitHub account was used to inspect `nandahtoon/Mifosx-web-app`, `nandahtoon/MicroOps-Infra`, and `nandahtoon/MicroOps-360-Fineract-Org`. The web AGENTS contract confirms Odoo as a separate bounded consumer, native Fineract APIs, synthetic staging, and explicit LIVE/EMPTY/ERROR/DEMO presentation. The infrastructure profile and read-only workflow identify canonical Oracle staging; the program charter and Fineract-first direction establish authority and evidence gates. No changes were made in those repositories. See ORACLE-STAGING.md for exact source paths, live public provenance and the authenticated-access limitation.
