from django.test import TestCase, override_settings


class SignupWithoutEmailConfigTests(TestCase):
    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
        DEFAULT_FROM_EMAIL='noreply@example.com',
    )
    def test_signup_works_without_smtp_credentials(self):
        response = self.client.post(
            '/api/signup/',
            {
                'username': 'newuser',
                'email': 'newuser@example.com',
                'password': 'strongpass123',
                'password_confirm': 'strongpass123',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 202)
        self.assertIn('Check your email to verify it.', response.json()['message'])
