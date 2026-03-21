import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, test } from '@playwright/test';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const imageFixture = path.resolve(__dirname, '../../../data/test_image.ppm');

test('seeded model-backed coordinator and volunteer flows work end to end', async ({ page }) => {
  page.on('dialog', async (dialog) => {
    await dialog.accept();
  });

  await page.goto('/coordinator-login');
  await page.getByTestId('coordinator-email').fill('coordinator@test.com');
  await page.getByTestId('coordinator-password').fill('password');
  await page.getByRole('button', { name: 'Sign In' }).click();

  await page.getByRole('button', { name: 'Dashboard' }).click();
  await expect(page.getByText('Broken Handpump Near School')).toBeVisible();
  await expect(page.getByText('Digital Literacy Camp')).toBeVisible();

  await page.getByTestId('problem-search-input').fill('Digital Literacy');
  await expect(page.getByText('Digital Literacy Camp')).toBeVisible();
  await expect(page.getByText('Broken Handpump Near School')).not.toBeVisible();
  await page.getByTestId('problem-search-input').fill('');

  await page.getByRole('button', { name: 'Pending' }).click();
  await expect(page.getByText('Drainage Repair Near Market')).not.toBeVisible();

  const digitalProblemCard = page.getByTestId('problem-card-PROB-002');
  await digitalProblemCard.getByRole('button', { name: /Assign Team/i }).click();
  await page.getByTestId('generate-optimal-teams').click();
  await expect(page.getByText(/Severity:/)).toBeVisible();
  await page.getByTestId('assign-ai-team-1').click();
  await expect(page.getByText('Assign Resolution Team')).not.toBeVisible();

  await page.getByRole('button', { name: 'New Problem' }).click();
  await page.getByTestId('village-name-input').fill('Riverbend');
  await page.getByTestId('village-address-input').fill('Ward 4 Riverbank');
  await page.getByTestId('problem-title-input').fill('Image Verified Complaint');
  await page.getByRole('button', { name: 'Health' }).click();
  await page.getByTestId('problem-description-input').fill('Uploaded image should trigger visual tags and allow submission.');
  await page.getByTestId('problem-image-input').setInputFiles(imageFixture);
  await expect(page.getByTestId('image-analysis-tags')).toBeVisible();
  await page.getByRole('button', { name: 'Submit Problem' }).click();
  await expect(page.getByText('Submitted Successfully!')).toBeVisible();

  await page.getByRole('button', { name: 'Logout' }).click();
  await page.goto('/volunteer-login');
  await page.getByTestId('volunteer-email').fill('volunteer@test.com');
  await page.getByTestId('volunteer-password').fill('password');
  await page.getByRole('button', { name: 'Sign In' }).click();

  await page.getByRole('button', { name: 'My Tasks' }).click();
  const assignedTask = page.getByText('Digital Literacy Camp');
  await expect(assignedTask).toBeVisible();
  await assignedTask.click();
  await page.getByTestId('before-photo-input').setInputFiles(imageFixture);
  await page.getByTestId('after-photo-input').setInputFiles(imageFixture);
  await page.getByRole('button', { name: 'Submit Resolution Proof' }).click();
  await expect(page.getByText('Digital Literacy Camp')).toBeVisible();
  await expect(page.getByText('completed')).toBeVisible();
});
