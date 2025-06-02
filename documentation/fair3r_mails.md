# HTML Email Support for CKAN

ckanext/lib/mailer.py enhance CKAN's email functionality by providing HTML email support.

## Overview

The `mailer.py` module overrides CKAN's default email functions to send HTML emails. This allows for more visually appealing emails with better user experience.

## How it Works

1. **HTML Templates**: HTML versions of email templates are stored in `ckanext/fair3r/templates/emails/html/`.

2. **Custom Mailer Functions**: The `mailer.py` module provides custom versions of CKAN's email functions:
   - `send_reset_link()`: Sends password reset emails with HTML content
   - `send_invite()`: Sends invitation emails with HTML content

3. **Monkey Patching**: The `Fair3RPlugin` class in `plugin.py` overrides CKAN's default mailer functions with our custom ones when the plugin is loaded.

## Email Templates

### HTML Templates
- `emails/html/reset_password.html`: HTML password reset email
- `emails/html/invite_user.html`: HTML user invitation email

### Subject Templates
- `emails/reset_password_subject.txt`: Subject for password reset email
- `emails/invite_user_subject.txt`: Subject for invitation email

## Implementation Details

When a password reset or invitation email is sent:

1. The HTML version of the email body is generated
2. The email is created with the HTML content
3. The email is sent to the user

## Customization

To customize the appearance of HTML emails:

1. Edit the HTML templates in `ckanext/fair3r/templates/emails/html/`
2. Modify the inline CSS styles in the templates to change colors, fonts, spacing, etc.
3. Update the `mailer.py` module if you need to change how emails are generated or sent
