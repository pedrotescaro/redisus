import { expect, test } from '@playwright/test';

test('abre a tela de login', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByRole('button', { name: /entrar/i })).toBeVisible();
});
