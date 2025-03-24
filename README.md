[![Tests](https://github.com/ICS/ckanext-fair3r/workflows/Tests/badge.svg?branch=main)](https://github.com/ICS/ckanext-fair3r/actions)

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

    git+http://gitlab+deploy-token-14:REDACTED-DEPLOY-TOKEN@serv-gitlab.igbmc.u-strasbg.fr//ics/ckanext-fair3r.git
    cd ckanext-fair3r
    pip install -e .
	pip install -r requirements.txt

3. Add `fair3r` to the `ckan.plugins` setting in your CKAN
   config file (by default the config file is located at
   `/etc/ckan/default/ckan.ini`).

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu:

     sudo service apache2 reload


## Config settings

	# The app context (could be DEV, DEMO, or nothing)
	ckanext.fair3r.some_setting = DEV


## Developer installation

To install ckanext-fair3r for development, activate your CKAN virtualenv and
do:

    git clone git@serv-gitlab.igbmc.u-strasbg.fr:ics/ckanext-fair3r.git
    cd ckanext-fair3r
    python setup.py develop
    pip install -r dev-requirements.txt


## Tests

To run the tests, do:

    pytest --ckan-ini=test.ini


## Releasing a new version of ckanext-fair3r

If ckanext-fair3r should be available on PyPI you can follow these steps to publish a new version:

1. Update the version number in the `setup.py` file. See [PEP 440](http://legacy.python.org/dev/peps/pep-0440/#public-version-identifiers) for how to choose version numbers.

2. Make sure you have the latest version of necessary packages:

    pip install --upgrade setuptools wheel twine

3. Create a source and binary distributions of the new version:

       python setup.py sdist bdist_wheel && twine check dist/*

   Fix any errors you get.

4. Upload the source distribution to PyPI:

       twine upload dist/*

5. Commit any outstanding changes:

       git commit -a
       git push

6. Tag the new release of the project on GitHub with the version number from
   the `setup.py` file. For example if the version number in `setup.py` is
   0.0.1 then do:

       git tag 0.0.1
       git push --tags

## License

[AGPL](https://www.gnu.org/licenses/agpl-3.0.en.html)
