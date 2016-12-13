Core condoor components
=======================

.. automodule:: condoor

Connection class
----------------

.. autoclass:: Connection

   .. automethod:: __init__
   .. automethod:: connect
   .. automethod:: discovery
   .. automethod:: reconnect
   .. automethod:: disconnect
   .. automethod:: reload
   .. automethod:: send
   .. automethod:: enable
   .. automethod:: run_fsm

   .. autoattribute:: family
   .. autoattribute:: platform
   .. autoattribute:: os_type
   .. autoattribute:: os_version
   .. autoattribute:: hostname
   .. autoattribute:: prompt
   .. autoattribute:: is_connected
   .. autoattribute:: is_console
   .. autoattribute:: name
   .. autoattribute:: description
   .. autoattribute:: pid
   .. autoattribute:: vid
   .. autoattribute:: sn
   .. autoattribute:: udi
   .. autoattribute:: device_info
