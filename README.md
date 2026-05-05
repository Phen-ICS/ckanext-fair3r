# ckanext-fair3r

This extension is made to cuztomize fair3r.fr ckan theme and add features

## Requirements

Compatibility with core CKAN versions:

| CKAN version    | Compatible? |
|-----------------|-------------|
| 2.10.7          | yes         |
| 2.11            | not tested  |


## Installation

To install ckanext-fair3r:

1. Activate your CKAN virtual environment, for example:

     . /usr/lib/ckan/default/bin/activate

2. Clone the source and install it on the virtualenv

    git clone git@serv-gitlab.igbmc.u-strasbg.fr:ics/ckanext-fair3r.git
    cd ckanext-fair3r
    pip install -e .
	pip install -r requirements.txt

3. Add `fair3r` to the `ckan.plugins` setting in your CKAN
   config file (by default the config file is located at
   `/etc/ckan/default/ckan.ini`).

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu:

     sudo service apache2 reload


## Config settings

    exemple: 

	# The app context (could be DEV, INTEGRATION, VALIDATION, or PRODUCTION)
	ckanext.fair3r.context = DEV


## Developer installation

To install ckanext-fair3r for development, activate your CKAN virtualenv and
do:

    git clone git@serv-gitlab.igbmc.u-strasbg.fr:ics/ckanext-fair3r.git
    cd ckanext-fair3r
    python setup.py develop
    pip install -r dev-requirements.txt


## Tests

TODO