include virtualenv.mk

all: tests

tests:
	$(DJANGO_REST_RESOURCES_VE)/bin/nosetests --with-coverage --cover-package=resources ./resources/test

clean:
	-find -name "*.pyc" -exec rm '{}' ';'

bootstrap:
	virtualenv --python=$(PYTHON) $(DJANGO_REST_RESOURCES_VE)
	$(DJANGO_REST_RESOURCES_VE)/bin/pip install -r requirements.txt

upload:
	$(DJANGO_REST_RESOURCES_VE)/bin/python setup.py sdist upload
