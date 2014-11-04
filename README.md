# Magnificent Octopus

Used for building Flask-based applications which may want to talk to an Elasticsearch back-end, and want to 
integrate with all kinds of external services.

## Root Configuration

The root configuration tells Magnificent Octopus where to load the module configurations from, and where to serve Jinja templates and static files from.

It also details scripts to run during application initialisation (i.e. post-configuration but pre-execution).  See the section **Initialisation** below.

The built-in configuration will load the config for all known modules and libraries.  You can override this by providing your own one in the environment variable APP_CONFIG at startup.

It provides ONLY the following configuration options:

```python
    # absolute paths, or relative paths from root directory, to the desired config files (in the order you want them loaded)
    CONFIG_FILES = [
        "... lib and module configs ...",
        "config/service.py",
        "local.cfg"
    ]
    
    # absolute paths, or relative paths from root directory, to the template directories (in the order you want them looked at)
    TEMPLATE_PATHS = [
        "service/templates",
        "magnificent-octopus/octopus/templates"
    ]
    
    # absolute paths, or relative paths from the root directory, to the static file directories (in the order you want them looked at)
    STATIC_PATHS = [
        "service/static",
        "magnificent-octopus/octopus/static"
    ]
    
    # module import paths for the startup modules that need to run at application init type (in the order you want them run)
    INITIALISE_MODULES = [
        "octopus.modules.es.initialise"
    ]
```

## Initialisation

After the app has been created and configured, but before it is run, it needs to be initialised.  In all scripts and modules which require the application to be in a known full-operational state, you will need to run the initialise script first.

```python
    from octopus.core import app, initialise
    initialise()
```

This will load all the modules specified in the**INITIALISE_MODULES** config in the root configuration (see above).  It will then execute their "initialise" function; each module which requires initialisation must provide its own initialisation routine.

To create an initialise routine just supply a function as follows

```python
    from octopus.core import app
    def initialise():
        # do your initialisation operations
        # this function should be idempotent
        pass
```

## JavaScript configuration

In order that the standard JavaScript modules work correctly, they need their configuration to be set in the javascript config file.  This can be found at:

    octopus/templates/js/config.js
    
It is a jinja2 template, so when adding new things to it, you can use template semantics.  If you plan to override this config, you should copy it into the service/templates directory in the same location, and it will override the standard one.

## Library code

The octopus.lib directory contains helper libraries for building your applications.  See the [README](https://github.com/richard-jones/magnificent-octopus/tree/master/octopus/lib/README.md) for details

## Modules

The following modules are available (follow the links to their README files for more details)

### Elasticsearch

**module**: [octopus.modules.es](https://github.com/richard-jones/magnificent-octopus/tree/master/octopus/modules/es/README.md)

Used for providing direct access to the Elasticsearch back-end.  Implements a read-only query endpoint, and autocomplete features.  Also provides front-end javascript functions for querying the back-end features.

### Examples

**module**: [octopus.modules.examples](https://github.com/richard-jones/magnificent-octopus/tree/master/octopus/modules/examples/README.md)

Provides working examples of bits of the other modules available here

### Sherpa Fact

**module**: [octopus.modules.sherpafact](https://github.com/richard-jones/magnificent-octopus/tree/master/octopus/modules/sherpafact/README.md)

Provides a client library for accessing the Sherpa FACT API.