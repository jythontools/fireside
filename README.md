# Fireside

Blazing fast Servlet 3.x API for WSGI apps running on Jython that
works with standard setuptools. Note this is not a direct replacement
for ModJy, which offers more support for other types of setups (but
not readily for working with setuptools).

Some initial documentation on how to use Fireside is found in the
[HelloWSGI][] sample application.

# Building, with tests

Currently building requires the following steps:

  1. Execute the shell script `setup.sh`; this will build the
     supporting jar for Fireside (currently fireside-0.1.jar) using
     Gradle and downloads the required dependencies,
     `javax.servlet-api-3.1.0.jar` and `guava-19.0.jar`

  2. Set up your `CLASSPATH`: `. ./classpath.sh` - this will add the
     above jars accordingly

  3. `jython setup.py install`

  4. `jython setup.py test`  # which implies the above

The tests are written to work with Nose.

Real soon now, Clamp should have Gradle integration to eliminate steps 1 and 2.


<!--references-->

[HelloWSGI]: https://github.com/jimbaker/hellowsgi



