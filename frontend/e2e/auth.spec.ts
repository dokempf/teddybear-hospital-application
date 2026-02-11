import { expect, test } from '@playwright/test';

test.describe('authentication flow', () => {
	test('redirects unauthenticated users to the login page', async ({ page }) => {
		await page.goto('/');

		await expect(page).toHaveURL(/\/login\/?$/);
		await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
	});

	test('renders login controls for unauthenticated users', async ({ page }) => {
		await page.goto('/login');

		await expect(page.getByLabel('Password:')).toBeVisible();
		await expect(page.getByRole('button', { name: 'Login' })).toBeVisible();
	});

	test('keeps authenticated users on protected pages', async ({ page }) => {
		await page.addInitScript(() => {
			window.localStorage.setItem('session', 'playwright-seeded-session');
		});

		await page.goto('/');

		await expect(page).toHaveURL('/');
		await expect(page.getByRole('heading', { level: 1 })).toContainText('Teddy Hospital');
	});
});
