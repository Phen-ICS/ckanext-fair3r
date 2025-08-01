# Dataset Creation Choice Functionality

This document describes the new dataset creation choice functionality that allows users to choose between the standard CKAN form and the enhanced FCO interface.

## Overview

When users click "Add Dataset" in CKAN, they are now presented with a choice page that offers two options:

1. **Standard CKAN Form** - Available to all authenticated users
2. **Enhanced FCO Interface** - Available only to superadmins

## Features

### Choice Page
- Clean, modern interface with card-based layout
- Clear descriptions of each option
- Visual icons to distinguish between options
- Responsive design that works on all devices

### Access Control
- **Standard CKAN Form**: Available to all authenticated users
- **FCO Interface**: Restricted to superadmins only
- Non-superadmins see an informational message about FCO being admin-only

### Security
- Superadmin check is performed both in the template and in the backend
- Direct access to FCO routes is protected with superadmin verification
- Failed access attempts are logged for security monitoring

## Implementation Details

### Template Changes
- **File**: `ckanext/fair3r/templates/package/new.html`
- **Features**: 
  - Bootstrap-based responsive layout
  - Conditional rendering based on user permissions
  - Clear call-to-action buttons
  - Informational sidebar

### Plugin Changes
- **File**: `ckanext/fair3r/plugin.py`
- **Added**: `is_superadmin()` helper function
- **Purpose**: Check if current user has superadmin privileges

### Blueprint Changes
- **File**: `ckanext/fair3r/blueprints/fco_integration.py`
- **New Routes**:
  - `/dataset/new` - Shows choice page
  - `/dataset/new/fco` - Redirects to FCO (superadmin only)
  - `/dataset/new/standard` - Direct access to CKAN form
- **Security**: Superadmin verification on FCO routes

## User Flow

### For Regular Users
1. Click "Add Dataset" in CKAN
2. See choice page with only CKAN form option
3. Click "Use CKAN Form" to proceed
4. Use standard CKAN dataset creation interface

### For Superadmins
1. Click "Add Dataset" in CKAN
2. See choice page with both options
3. Choose either:
   - "Use CKAN Form" for standard interface
   - "Use FCO Interface" for enhanced interface
4. Proceed with chosen method

## Configuration

The functionality respects the existing FCO integration configuration:

```ini
# Enable/disable FCO integration
ckanext.fair3r.enable_fco_integration = true

# FCO application URL
ckanext.fair3r.fco_url = http://localhost:8080

# Shared secret for secure communication
ckanext.fair3r.shared_secret = your-secret-key
```

## Testing

### Manual Testing
1. **As Regular User**:
   - Log into CKAN as a non-superadmin user
   - Visit `/dataset/new`
   - Verify only CKAN form option is visible
   - Verify FCO option is not shown

2. **As Superadmin**:
   - Log into CKAN as a superadmin user
   - Visit `/dataset/new`
   - Verify both options are visible
   - Test both options work correctly

3. **Direct Access Testing**:
   - Try accessing `/dataset/new/fco` as non-superadmin
   - Verify access is denied and user is redirected
   - Check logs for security warnings

### Automated Testing
Run the test script:
```bash
cd /opt/ckan/lib/default/src/ckanext-fair3r
python test_dataset_creation_choice.py
```

## Security Considerations

### Access Control
- Superadmin status is verified both in template and backend
- Direct route access is protected with server-side verification
- Failed access attempts are logged for monitoring

### User Experience
- Clear messaging about access restrictions
- Graceful fallback for unauthorized access
- Consistent user experience across different permission levels

## Troubleshooting

### Common Issues

1. **FCO option not visible to superadmin**
   - Check if user has `sysadmin=True` in database
   - Verify FCO integration is enabled in configuration
   - Check application logs for errors

2. **Choice page not loading**
   - Verify template is properly installed
   - Check if blueprint is registered correctly
   - Ensure user is authenticated

3. **FCO redirect not working**
   - Verify FCO application is running
   - Check FCO URL configuration
   - Verify shared secret matches between applications

### Debug Commands

```bash
# Check user permissions
ckan user show username

# Check FCO integration status
curl http://localhost:5000/fco/status

# Check FCO application status
curl http://localhost:8080/ckan/status
```

## Future Enhancements

### Planned Features
1. **User Preferences**: Remember user's preferred method
2. **Analytics**: Track which method users prefer
3. **Customization**: Allow organizations to customize available options
4. **Workflow Integration**: Support for approval workflows

### Integration Extensions
1. **Bulk Operations**: Enhanced bulk dataset creation
2. **Templates**: Pre-defined dataset templates
3. **Validation**: Enhanced data validation rules
4. **Notifications**: Email notifications for dataset events

## Files Modified

### New Files
- `ckanext/fair3r/templates/package/new.html` - Choice page template
- `test_dataset_creation_choice.py` - Test script
- `DATASET_CREATION_CHOICE.md` - This documentation

### Modified Files
- `ckanext/fair3r/plugin.py` - Added superadmin helper
- `ckanext/fair3r/blueprints/fco_integration.py` - Updated routes

## Summary

The dataset creation choice functionality provides a clean, secure way for users to choose between standard CKAN and enhanced FCO interfaces. The implementation ensures proper access control while maintaining a good user experience for all user types. 