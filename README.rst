ITK export
==========

This is a plugin for `pretix`_.

Post-installion
---------------

Required settings in [Pretix Configuration file](https://docs.pretix.eu/en/latest/admin/config.html):

.. code-block::

  [itk_export]
  ; Drift skal krediteres hvis der er tale om en indtægt
  credit_artskonto=…
  ; banken skal debiteres.
  debit_artskonto=…

  ; "mellemregningskonto"
  cash_artskonto=…


To make a non-empty “PSP” metadata value read-only, you have to use a custom template for event settings:

.. code-block::

  cd «your `data` folder»
  mkdir -p templates/pretixcontrol/event/
  ln -sf $VIRTUAL_ENV/src/pretix-itk-export/pretix_itkexport/templates/pretixcontrol/event/settings.html templates/pretixcontrol/event/


Usage
-----

.. code-block::

  LC_ALL=da_DK.UTF-8 python manage.py itk-export --help


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
