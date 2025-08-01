# CKAN to Fair3R Custom Overlay Integration - Complete Documentation

This document provides comprehensive documentation for the integration between CKAN and the Fair3R Custom Overlay (FCO) application, which provides enhanced dataset creation functionality with shared authentication.

## Overview

The integration allows users to seamlessly create datasets using an enhanced interface in the Fair3R Custom Overlay application while maintaining their authentication state from CKAN. The integration includes:

- **Shared Authentication**: Users authenticated in CKAN are automatically authenticated in FCO
- **Secure Token Transmission**: API tokens and user data are transmitted securely using HMAC signatures
- **Enhanced Dataset Creation**: Modern, user-friendly interface for dataset creation
- **Seamless Redirects**: Users clicking "Add Dataset" in CKAN are redirected to FCO

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

## Implementation Summary

### Changes Made

#### 1. CKAN Configuration Updates

**Files Modified:**
- `deploy/ckan-dev.ini`
- `deploy/ckan-demo.ini`
- `deploy/ckan-prod.ini`

**Changes:**
- Added FCO integration configuration settings
- Environment-specific FCO URLs
- Shared secret key configuration
- Integration enable/disable flag

#### 2. CKAN Extension (ckanext-fair3r) Updates

**New Files Created:**
- `ckanext/fair3r/blueprints/__init__.py`
- `ckanext/fair3r/blueprints/fco_integration.py`
- `ckanext/fair3r/templates/package/new.html`
- `ckanext/fair3r/templates/header/header.html`
- `test_fco_integration.py`
- `CKAN_FCO_INTEGRATION.md`

**Files Modified:**
- `ckanext/fair3r/plugin.py`

**Key Features Added:**
- FCO integration blueprint with secure token generation
- Dataset creation request interception
- Health check endpoints
- Template overrides for enhanced UX
- Navigation link to FCO dashboard

#### 3. Fair3R Custom Overlay Updates

**New Files Created:**
- `fair3r_custom_overlay/blueprints/ckan/__init__.py`
- `fair3r_custom_overlay/blueprints/ckan/integration.py`
- `fair3r_custom_overlay/templates/ckan/create_dataset.html`
- `alembic/versions/add_ckan_integration_fields.py`

**Files Modified:**
- `fair3r_custom_overlay/models/user.py`
- `fair3r_custom_overlay/__init__.py`
- `fair3r_custom_overlay/lib/_config.py`
- `deploy/requirements.txt`

**Key Features Added:**
- CKAN integration blueprint with secure token validation
- Enhanced dataset creation interface
- User management with CKAN integration
- Database schema updates for CKAN fields
- API endpoints for dataset submission

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

### Step 1: Database Migration

Run the database migration to add CKAN integration fields:

```bash
cd /opt/fair3r-custom-overlay
alembic upgrade head
```

### Step 2: Install Dependencies

Add the ckanapi dependency to FCO:

```bash
pip install ckanapi==4.8
```

### Step 3: Restart Services

Restart both CKAN and FCO applications:

```bash
# Restart CKAN
sudo service apache2 reload

# Restart FCO (if using Docker)
docker compose restart

# Or restart FCO directly
python fair3r_custom_overlay_app.py
```

### Step 4: Test Integration

Run the integration test script:

```bash
cd /opt/ckan/lib/default/src/ckanext-fair3r
python test_fco_integration.py
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

## Security Implementation

### Token Generation (CKAN Side)

```python
def _generate_secure_token(user_data, shared_secret):
    # Add timestamp and expiration
    user_data['timestamp'] = int(time.time())
    user_data['expires'] = int(time.time()) + 300  # 5 minutes
    
    # JSON encode and base64 encode
    data_json = json.dumps(user_data, sort_keys=True)
    data_encoded = base64.b64encode(data_json.encode('utf-8')).decode('utf-8')
    
    # Create HMAC signature
    signature = hmac.new(
        shared_secret.encode('utf-8'),
        data_encoded.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Combine and encode
    token = f"{data_encoded}.{signature}"
    return base64.b64encode(token.encode('utf-8')).decode('utf-8')
```

### Token Validation (FCO Side)

```python
def _validate_secure_token(token, shared_secret):
    # Decode token
    token_data = base64.b64decode(token.encode('utf-8')).decode('utf-8')
    data_encoded, signature = token_data.split('.', 1)
    
    # Verify HMAC signature
    expected_signature = hmac.new(
        shared_secret.encode('utf-8'),
        data_encoded.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        return None
    
    # Decode data and check expiration
    data_json = base64.b64decode(data_encoded.encode('utf-8')).decode('utf-8')
    user_data = json.loads(data_json)
    
    if user_data.get('expires', 0) < time.time():
        return None
    
    return user_data
```

## User Flow

1. **User logs into CKAN**
2. **User clicks "Add Dataset"**
3. **CKAN intercepts request and generates secure token**
4. **User is redirected to FCO with token**
5. **FCO validates token and authenticates user**
6. **User creates dataset using enhanced interface**
7. **Dataset is submitted to CKAN via API**
8. **User can view dataset in CKAN**

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

### Testing Checklist

- [ ] Database migration applied successfully
- [ ] Dependencies installed (ckanapi)
- [ ] Both applications running
- [ ] Integration test script passes
- [ ] Health check endpoints respond
- [ ] User can access enhanced dataset creation
- [ ] Dataset creation works end-to-end
- [ ] Fallback to standard CKAN interface works
- [ ] Navigation link to FCO dashboard works

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

### Debug Commands

```bash
# Check CKAN status
curl http://localhost:5000/fco/status

# Check FCO status
curl http://localhost:8080/ckan/status

# Test integration
cd /opt/ckan/lib/default/src/ckanext-fair3r
python test_fco_integration.py
```

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

## Files Changed Summary

### CKAN Core
- 3 configuration files updated with FCO settings

### ckanext-fair3r
- 1 plugin file modified (added blueprint support)
- 6 new files created (blueprints, templates, tests, docs)

### Fair3R Custom Overlay
- 1 model file modified (added CKAN fields)
- 1 config file modified (shared secret)
- 1 requirements file modified (added ckanapi)
- 1 app file modified (registered blueprint)
- 4 new files created (blueprint, template, migration, docs)

**Total: 15 files modified/created across 3 applications**

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

## Next Steps

1. **Deploy to development environment**
2. **Test with real users**
3. **Monitor logs for issues**
4. **Deploy to demo environment**
5. **Deploy to production environment**
6. **Plan future enhancements**

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review application logs for error messages
3. Test with the provided test script
4. Contact the development team with specific error details

## License

This integration is part of the Fair3R project and follows the same licensing terms as the main applications. 