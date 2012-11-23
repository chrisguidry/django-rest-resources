include virtualenv.mk

all: tests

tests:
	$(DJANGO_RESOURCES_VE)/bin/nosetests --with-coverage --cover-package=resources ./resources/test

clean:
	-find -name "*.pyc" -exec rm '{}' ';'

bootstrap:
	virtualenv --python=$(PYTHON) $(DJANGO_RESOURCES_VE)
	$(DJANGO_RESOURCES_VE)/bin/pip install -r requirements.txt
