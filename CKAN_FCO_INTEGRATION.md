# CKAN to Fair3R Custom Overlay Integration

This document describes the integration between CKAN and the Fair3R Custom Overlay (FCO) application, which provides enhanced dataset creation functionality with shared authentication.

## Overview

The integration allows users to seamlessly create datasets using an enhanced interface in the Fair3R Custom Overlay application while maintaining their authentication state from CKAN. The integration includes:

- **Shared Authentication**: Users authenticated in CKAN are automatically authenticated in FCO
- **Secure Token Transmission**: API tokens and user data are transmitted securely using HMAC signatures
- **Enhanced Dataset Creation**: Modern, user-friendly interface for dataset creation
- **Seamless Redirects**: Users clicking "Add Dataset" in CKAN are redirected to FCO
- **Fallback Support**: Users can still access the standard CKAN dataset creation interface

## Architecture

### Components

1. **CKAN Extension (ckanext-fair3r)**
   - Intercepts dataset creation requests
   - Generates secure tokens with user data
   - Redirects users to FCO
   - Provides health check endpoints

2. **Fair3R Custom Overlay (FCO)**
   - Validates secure tokens from CKAN
   - Creates/updates user records with CKAN data
   - Provides enhanced dataset creation interface
   - Submits datasets back to CKAN via API

3. **Shared Configuration**
   - Common SECRET_KEY for secure token generation/validation
   - Environment-specific FCO URLs
   - Integration enable/disable settings

### Security Model

- **HMAC Signatures**: All tokens are signed with a shared secret
- **Time-based Expiration**: Tokens expire after 5 minutes
- **Secure Transmission**: User data is base64 encoded and signed
- **API Token Storage**: CKAN API tokens are stored encrypted in FCO database

## Configuration

### CKAN Configuration

Add the following settings to your CKAN configuration files:

```ini
## Fair3R Custom Overlay Integration Settings ##################################
# FCO application URL for dataset creation redirects
ckanext.fair3r.fco_url = http://localhost:8080
# Shared secret key for secure token transmission (must match FCO SECRET_KEY)
ckanext.fair3r.shared_secret = 5#yqsj4de85s6zzjkncwhjciksd
# Enable FCO integration for dataset creation
ckanext.fair3r.enable_fco_integration = true
```

**Environment-specific URLs:**
- **Development**: `http://localhost:8080`
- **Demo**: `http://serv-ics-fco-d-01`
- **Production**: `http://serv-ics-fco-p-01`

### FCO Configuration

The FCO application uses the same SECRET_KEY as CKAN:

```python
# In fair3r_custom_overlay/lib/_config.py
SECRET_KEY = '5#yqsj4de85s6zzjkncwhjciksd'
```

## Installation

### 1. Database Migration

Run the database migration to add CKAN integration fields:

```bash
cd /opt/fair3r-custom-overlay
alembic upgrade head
```

### 2. Install Dependencies

Add the ckanapi dependency to FCO:

```bash
pip install ckanapi==4.8
```

### 3. Restart Services

Restart both CKAN and FCO applications:

```bash
# Restart CKAN
sudo service apache2 reload

# Restart FCO (if using Docker)
docker compose restart

# Or restart FCO directly
python fair3r_custom_overlay_app.py
```

## Usage

### For Users

1. **Log into CKAN** with your credentials
2. **Click "Add Dataset"** in the CKAN interface
3. **Automatic Redirect**: You'll be redirected to the enhanced FCO interface
4. **Create Dataset**: Use the enhanced form to create your dataset
5. **Automatic Submission**: The dataset is automatically created in CKAN
6. **Return to CKAN**: You can view your dataset in the standard CKAN interface

### For Administrators

#### Enable/Disable Integration

To disable the integration temporarily:

```ini
ckanext.fair3r.enable_fco_integration = false
```

#### Health Checks

Check integration status:

- **CKAN Status**: `http://localhost:5000/fco/status`
- **FCO Status**: `http://localhost:8080/ckan/status`

#### Direct Access

Users can access the standard CKAN interface directly:

- **Standard CKAN**: `http://localhost:5000/dataset/new/ckan`
- **FCO Dashboard**: `http://localhost:8080` (link in CKAN header)

## API Endpoints

### CKAN Endpoints

- `GET /dataset/new` - Intercepted by FCO integration
- `GET /dataset/new/ckan` - Direct access to CKAN dataset creation
- `GET /fco/status` - Integration status check

### FCO Endpoints

- `GET /ckan/integration` - Handle CKAN integration requests
- `GET /ckan/create_dataset` - Enhanced dataset creation interface
- `POST /ckan/submit_dataset` - Submit dataset to CKAN
- `GET /ckan/organizations` - Get available organizations
- `GET /ckan/status` - Integration status check

## Database Schema

### New User Fields

The FCO user table has been extended with CKAN integration fields:

```sql
ALTER TABLE users ADD COLUMN ckan_user_id VARCHAR(100) UNIQUE;
ALTER TABLE users ADD COLUMN ckan_username VARCHAR(100);
ALTER TABLE users ADD COLUMN ckan_api_token VARCHAR(500);
ALTER TABLE users ADD COLUMN ckan_site_url VARCHAR(200);
```

### User Management

- **Automatic Creation**: Users are automatically created in FCO when they first access the integration
- **Token Storage**: CKAN API tokens are stored securely in the FCO database
- **User Linking**: Users are linked by their CKAN user ID for seamless authentication

## Security Considerations

### Token Security

- **HMAC Signatures**: All tokens are signed with SHA256 HMAC
- **Time Expiration**: Tokens expire after 5 minutes to prevent replay attacks
- **Secure Storage**: API tokens are stored in the database (consider encryption for production)

### Authentication Flow

1. User authenticates in CKAN
2. CKAN generates secure token with user data
3. User is redirected to FCO with token
4. FCO validates token and authenticates user
5. User can create datasets using their CKAN API token

### Error Handling

- **Invalid Tokens**: Users are redirected to login
- **Expired Tokens**: Users are redirected to login
- **Connection Failures**: Graceful fallback to standard CKAN interface
- **API Errors**: Detailed error messages for debugging

## Testing

### Test Script

Run the integration test script:

```bash
cd /opt/ckan/lib/default/src/ckanext-fair3r
python test_fco_integration.py
```

### Manual Testing

1. **Start both applications**:
   ```bash
   # CKAN
   ckan -c /path/to/ckan.ini run
   
   # FCO
   python fair3r_custom_overlay_app.py
   ```

2. **Test the integration**:
   - Visit `http://localhost:5000/dataset/new`
   - You should be redirected to FCO
   - Create a dataset using the enhanced interface
   - Verify the dataset appears in CKAN

### Health Checks

Check the status of both applications:

```bash
# CKAN status
curl http://localhost:5000/fco/status

# FCO status
curl http://localhost:8080/ckan/status
```

## Troubleshooting

### Common Issues

1. **Integration not working**
   - Check that `ckanext.fair3r.enable_fco_integration = true`
   - Verify FCO URL is correct
   - Ensure both applications are running

2. **Authentication failures**
   - Check that SECRET_KEY matches in both applications
   - Verify user has valid CKAN API token
   - Check database migration was applied

3. **Dataset creation fails**
   - Verify CKAN API token is valid
   - Check user has permission to create datasets
   - Review CKAN logs for API errors

### Logs

Check application logs for errors:

```bash
# CKAN logs
tail -f /var/log/ckan/default/ckan.log

# FCO logs
tail -f /opt/fair3r-custom-overlay/logs/fair3r_custom_overlay.log
```

### Debug Mode

Enable debug mode for detailed error messages:

```ini
# CKAN
debug = true

# FCO (in config)
DEBUG = True
```

## Future Enhancements

### Planned Features

1. **Resource Upload**: Enhanced file upload interface
2. **Metadata Templates**: Pre-defined dataset templates
3. **Bulk Operations**: Create multiple datasets at once
4. **Advanced Validation**: Enhanced data validation
5. **Workflow Management**: Approval workflows for datasets

### Integration Extensions

1. **User Management**: Synchronize user profiles between applications
2. **Organization Management**: Enhanced organization interface
3. **Analytics**: Dataset usage analytics
4. **Notifications**: Email notifications for dataset events

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review application logs for error messages
3. Test with the provided test script
4. Contact the development team with specific error details

## License

This integration is part of the Fair3R project and follows the same licensing terms as the main applications. 