import { test, expect } from "@playwright/test";

test("command search opens from the header and returns focus when dismissed", async ({
  page,
}) => {
  await page.goto("./");
  const trigger = page.getByRole("button", { name: /search documentation/i });
  await expect(trigger).toBeVisible();
  await trigger.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: /search documentation/i });
  await expect(dialog).toBeVisible();
  const input = dialog.getByRole("searchbox");
  await expect(input).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
});

test("keyboard shortcut searches local docs and supports arrow navigation", async ({
  page,
}) => {
  await page.goto("./");
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: /search documentation/i });
  await expect(dialog).toBeVisible();
  const input = dialog.getByRole("searchbox");
  await input.fill("recovery privacy");
  const result = dialog.getByRole("link", { name: /recovery.*privacy/i });
  await expect(result).toBeVisible();
  await expect(result).toHaveAttribute("href", "/Orion/docs/recovery.html");
  await page.keyboard.press("ArrowDown");
  await expect(result).toHaveAttribute("aria-current", "true");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/Orion\/docs\/recovery\.html$/);
});

test("search is available on generated docs pages and reports no matches", async ({
  page,
}) => {
  await page.goto("./docs/install.html");
  await page.keyboard.press("Meta+k");
  const dialog = page.getByRole("dialog", { name: /search documentation/i });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("searchbox").fill("zzzz-no-such-guide");
  await expect(dialog.getByText(/no guides matched/i)).toBeVisible();
});

test("an unavailable local index leaves the dialog actionable", async ({
  page,
}) => {
  await page.route("**/docs/search-index.json", (route) => route.abort());
  await page.goto("./");
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: /search documentation/i });
  const input = dialog.getByRole("searchbox");
  await input.fill("install");
  await expect(dialog.getByText(/could not load/i)).toBeVisible();
  await expect(input).toBeEnabled();
  await expect(dialog.getByRole("button", { name: /close/i })).toBeEnabled();
  await expect(
    dialog.getByRole("link", { name: /browse all guides/i }),
  ).toHaveAttribute("href", "/Orion/docs/");
});
