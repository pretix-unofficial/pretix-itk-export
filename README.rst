ITK export
==========

This is a plugin for `pretix`_.

Usage
-----

.. code-block::

  LC_ALL=da_DK.UTF-8 python manage.py itk-export --help

Run weekly with cron:

.. code-block::

  0 2 * * TUE LC_ALL=da_DK.UTF-8 python manage itk-export --period=previous-week+1 --organizers test --credit-artskonto=3 --debit-artskonto=2 --cash-artskonto 1 --recipient=…@aarhus.dk > /dev/null 2>&1

Development setup
-----------------

1. Make sure that you have a working `pretix development setup`_.

2. Clone this repository, eg to ``local/pretix-itk-export``.

3. Activate the virtual environment you use for pretix development.

4. Execute ``python setup.py develop`` within this directory to register this application with pretix's plugin registry.

5. Execute ``make`` within this directory to compile translations.

6. Restart your local pretix server. You can now use the plugin from this repository for your events by enabling it in
   the 'plugins' tab in the settings.


License
-------

Copyright 2018 Mikkel Ricky

Released under the terms of the Apache License 2.0


.. _pretix: https://github.com/pretix/pretix
.. _pretix development setup: https://docs.pretix.eu/en/latest/development/setup.html
