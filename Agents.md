# Batumi Lunch Bot – Agents

## Telegram Conversation Agent (`bot.py`)

### Responsibilities
- Serves both end users and the administrator through a single `ConversationHandler`.
- Loads weekly menu data, walks customers through order placement, and forwards confirmed orders to the admin operator.
- Persists user profiles (address/phone), open orders, and conversation state for seamless restarts.
- Guards admin-only actions such as reports, broadcasts, and direct order manipulation.

### Customer Journey
1. **Entry** – `/start` or “🔄 В начало” shows branded welcome (photo optional) and main menu.
2. **Browse Menu** – “Показать меню на неделю” displays menu image/text, then prompts for a delivery day.
3. **Select Day & Count** – Guided choice via reply keyboards, with validation against `menu.json`.
4. **Provide Address & Phone** – Captured through text or Telegram contact share; saved to `users.json`.
5. **Confirm Order** – Summary includes menu, quantity, total cost (15₾ each), delivery window, and quick `/order <ID>` link.
6. **Post-Confirm** – Success animation (if `cat-driving.mp4` exists), cancellation inline button, and follow-up shortcuts.

### Admin Capabilities
- **Mode Toggle** – “Перейти в режим администратора/пользователя” keeps admin UI preference in `user_data`.
- **Weekly Reports** – “Показать заказы на эту неделю” + day selector to list active/cancelled orders for the current week.
- **Order Lookup** – `/order <ID>` and `/cancel <ID>` for owner/admin, plus inline cancellation button.
- **Broadcast** – `/sms <HTML message>` sends formatted announcements to combined user/order audience, excluding the admin.
- **Duplicate Resolution** – Detects existing order for the same user/day and offers to overwrite or increment quantity.
- **Profile Peek** – `/my_profile` dumps stored address/phone for quick verification.
- **Menu Management** – “Управление меню” entry point lets the admin rename the week, редактировать блюда, заменять фото меню и вручную открывать приём заказов на следующую неделю.

### Conversation States
| State    | Purpose                                                      | Key Handlers/Transitions |
|----------|--------------------------------------------------------------|---------------------------|
| `MENU`   | Landing actions, admin reports, contact operator             | `show_menu`, `order_lunch`, `admin_show_week_orders`, `contact_human` |
| `ORDER_DAY` | Pick delivery day                                         | `select_day`, `order_lunch` (restart), `contact_human` |
| `ORDER_COUNT` | Choose quantity or go back                              | `select_count`, `back_to_day`, `order_lunch` |
| `ADDRESS` | Collect address / phone                                     | `address_phone`, `back_to_count` |
| `CONFIRM` | Final confirmation, edit address/phone                      | `confirm_order`, `confirm_save_phone`, `confirm_request_phone` |
| `DUPLICATE` | Resolve conflicts with existing orders                    | `resolve_duplicate_order` |
| `ADMIN_MENU` | Manage weekly menu shell                                  | `admin_manage_menu`, `admin_menu_request_week`, `admin_menu_request_photo`, `admin_open_next_week_orders` |
| `ADMIN_MENU_DAY_SELECT` | Pick a day to edit                               | `admin_menu_day_chosen`, `admin_menu_back_to_main` |
| `ADMIN_MENU_ACTION` | Day-level actions                                  | `admin_menu_day_action_add/edit/delete/replace` |
| `ADMIN_MENU_ITEM_SELECT` | Await item index for edit/delete               | `admin_menu_handle_item_index` |
| `ADMIN_MENU_ITEM_TEXT` | Await free-form text (add/edit/replace items)   | `admin_menu_handle_text_input` |
| `ADMIN_MENU_WEEK` | Await new week title                                 | `admin_menu_save_week` |
| `ADMIN_MENU_PHOTO` | Await new menu photo                                | `admin_menu_handle_photo` |

The handler also wires fallbacks for unexpected input (`fallback`) and logs every reply-button click (`log_button`) for auditing.

### Error Handling
- Central `error_handler` suppresses noisy network issues, rate limits politely, and informs users on unhandled exceptions.

## Keyboard Layout Supplier (`keyboards.py`)
- Centralizes all reply keyboard definitions so text labels remain consistent across the conversation.
- Includes specialized keyboards for admin main screen, reports, duplicate resolution, and confirmation flows.

## Data & Persistence Layers

### Users Registry (`users.json`)
- Map of Telegram user ID → saved address/phone profile.
- Updated via `address_phone` and `confirm_save_phone`.
- Used for broadcasts and to pre-fill future orders.

### Orders Ledger (`orders.json`)
- Stores each order payload keyed by friendly ID (`make_order_id` format `BLB-<ts36>-<uid36>-<rnd>`).
- Tracks status (`new`, cancellation strings), creation timestamp, and menu snapshot.
- Admin reports filter by current week and day; duplicates check against non-cancelled orders this week.

### Weekly Menu (`menu.json`)
- JSON document with `week` label and `menu` map of weekday → dishes.
- `load_menu` + `save_menu` read/write helpers keep structure consistent and power the admin editing flow.

### Conversation Persistence (`bot_state.pickle`)
- `PicklePersistence` keeps conversation context (e.g., current state, pending order) across bot restarts.

## Configuration & Secrets
- `config.py` holds default paths, pricing constants, and placeholder welcome text.
- `config_secret.py` must define `BOT_TOKEN`, `ADMIN_ID`, and optional operator contact overrides. **Never commit real secrets**; rotate tokens if leaked.

## Logging & Diagnostics
- Root logger configured with `TimedRotatingFileHandler` under `logs/bot.log` plus concise console output.
- Helper `log_console` ensures notable milestones appear on stdout.
- User actions consistently logged with username/id for traceability.

## Operational Runbook
1. Ensure Python environment with `python-telegram-bot` v20+ (async) and `httpx`; activate virtualenv if present (`venv/`).
2. Populate `config_secret.py` with valid bot token, admin Telegram ID, and operator contact info.
3. Keep `menu.json` current either manually or through the Telegram admin workflow; refresh `Menu.jpeg` from the bot if desired (stored as `Menu.jpeg`).
4. Launch with `python bot.py`. Bot relies on long polling and will persist user conversations via pickle.
5. Monitor `logs/` for daily log files; rotate automatically (30-day retention). Investigate repeated network warnings or `BadRequest` entries.

## Extensibility Notes
- Adding new customer flows requires updating both `ConversationHandler` state lists and `BUTTONS_REGEX` to maintain logging.
- To introduce order status transitions (e.g., delivered), build on `set_order_status` and extend admin report formatting.
- Data schema changes should include migration logic or compatibility guards in `_load_users` / `_load_orders`.
