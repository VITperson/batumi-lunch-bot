# Release Notes — 2025-09-15

- Admin/user UI toggle for admin
  - Admins can switch between admin and user interfaces via buttons.
  - Mode persists across /start.

- “Мои заказы” (My Orders)
  - New button in the main menu and post‑order screen.
  - Shows only current‑week orders for today and later.
  - Clean layout with header, bullets, and copyable `/order <ID>` line.

- Order completion message
  - Removed the “Скопировать номер заказа” inline button.
  - Keeps a copyable `/order <ID>` line in the message body.

- Duplicate order resolution
  - If a user orders the same day again, the bot asks:
    - “Удалить предыдущий заказ” (cancel prior and proceed new), or
    - “Добавить к существующему” (increase quantity of the existing order).
  - Admin is notified on quantity updates and cancellations.

- Misc
  - Improved formatting for order listings.

