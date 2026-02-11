import { expect, test } from '@playwright/test';

test.describe('authenticated navigation', () => {
	test.beforeEach(async ({ page }) => {
		await page.addInitScript(() => {
			window.localStorage.setItem('session', 'seeded-playwright-session');
		});
	});

	test('loads home page and allows navigation to about', async ({ page }) => {
		await page.goto('/');

		await expect(page.getByRole('heading', { level: 1 })).toContainText('Teddy Hospital');
		await page.getByRole('link', { name: 'About' }).click();

		await expect(page).toHaveURL('/about');
		await expect(page.getByRole('heading', { name: 'About this app' })).toBeVisible();
	});

	test('shows footer docs link for authenticated users', async ({ page }) => {
		await page.goto('/');

		const docsLink = page.getByRole('link', { name: 'readthedocs page' });
		await expect(docsLink).toBeVisible();
		await expect(docsLink).toHaveAttribute(
			'href',
			'https://teddy-hospital-xray.readthedocs.io/en/latest/'
		);
	});
});
