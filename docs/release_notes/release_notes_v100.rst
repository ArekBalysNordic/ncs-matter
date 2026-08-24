.. _release_notes_v100:

Release notes for |addon| v1.0.0
################################

This page tracks changes and updates as compared to the latest official release.
For more information refer to the following section.

For the list of potential issues, see the :ref:`ncs_matter_known_issues` page.

Changelog
*********

This release provides Matter samples and documentation migrated from the |NCS| Matter.

* Added:

  * The Matter protocol documentation migrated from the |NCS| Matter user guide.
  * The Matter samples and applications migrated from the |NCS|.
  * The Matter configuration options migrated from the |NCS|.
  * The Matter software maturity levels migrated from the |NCS|.
  * The NFC Commissioning Manager implementation.
    See :ref:`ug_matter_configuring_optional_nfc` for more details.
  * Kconfig options to customize the Thread Network Diagnostics cluster attribute list.
    The ``ExtAddress`` and ``Rloc16`` attributes are optional in the Matter 1.6 specification, but the default Matter SDK implementation still exposes them in the cluster attribute list.
    Use the :option:`CONFIG_DISABLE_THREAD_DIAGNOSTIC_EXTADDR` or :option:`CONFIG_DISABLE_THREAD_DIAGNOSTIC_RLOC16` Kconfig options in your project configuration to omit them from the cluster attribute list.
  * Integration of |addon| with the |NCS| v3.4.0.

* Removed the :c:function:`Init` function from the :c:struct:`Nrf::Matter::IdentifyCluster` class.
  To add the Identify Matter cluster to your application, declare a new :c:struct:`Nrf::Matter::IdentifyCluster` object in your :file:`AppTask.c` file and fill all required constructor arguments.
