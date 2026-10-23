:orphan:

.. _migration_101:

Migration notes for |addon| v1.0.1
##################################

.. contents::
   :local:
   :depth: 3

This document describes changes required or recommended for migrating your Matter application from |addon| v1.0.0 to v1.0.1.

.. _migration_101_required:

Required changes
****************

The following changes are mandatory to make your application work in the same way as in previous releases.

Identify where the DAC private key is stored
============================================

Use the **first firmware** that completed factory-data migration on each device, not the Kconfig defaults of your current project alone.

+---------------------------+---------------------------------------------------------------------+
| First boot that migrated  | DAC private key location                                            |
| the DAC key               |                                                                     |
+===========================+=====================================================================+
| In-tree |NCS| Matter      | CRACEN KMU (expected on nRF54L with factory data)                   |
| (through |NCS| v3.4.0)    |                                                                     |
+---------------------------+---------------------------------------------------------------------+
| |addon| v1.0.0 on nRF54L  | PSA ITS (:kconfig:option:`CONFIG_CHIP_CRYPTO_PSA_DAC_PRIV_KEY_ITS`) |
+---------------------------+---------------------------------------------------------------------+

You can confirm the **current** firmware intent in :file:`build/<image>/zephyr/.config`:

* :kconfig:option:`CONFIG_CHIP_CRYPTO_PSA_DAC_PRIV_KEY_KMU` = ``y`` - Firmware migrates new keys to KMU.
* :kconfig:option:`CONFIG_CHIP_CRYPTO_PSA_DAC_PRIV_KEY_ITS` = ``y`` - Firmware migrates new keys to ITS.
* :kconfig:option:`CONFIG_CHIP_CRYPTO_PSA_DAC_PRIV_KEY_FALLBACK` = ``y`` - If the DAC private key is in a different backend than the selected one (ITS instead of KMU, or KMU instead of ITS), the legacy key is still used for signing (default in v1.0.1).

Choose a migration path
=======================

There are three possible migration paths, depending on the device's firmware and DAC key storage location.

Path A — Device previously on in-tree |NCS| Matter (key in KMU), updated to v1.0.0
----------------------------------------------------------------------------------

**Symptom:** Re-commissioning after performing factory reset fails after DFU.
Attestation errors such as ``OpCreds: Failed AttestationRequest request with IM error 0x01 (err = ac)`` occur.
Existing Matter fabrics may still operate.

**Action:** Deploy |addon| v1.0.1 (or newer) firmware.
With the :kconfig:option:`CONFIG_CHIP_CRYPTO_PSA_DAC_PRIV_KEY_FALLBACK` Kconfig option enabled (default), the device finds the key in KMU even if the ITS backend is selected.
Restoring the KMU defaults is still recommended, so that the selected backend matches the key location.

Path B — Product shipped or first flashed with |addon| v1.0.0 on nRF54L series device (key in ITS)
--------------------------------------------------------------------------------------------------

Until each unit is re-provisioned with new factory data (new DAC key and certificates), choose one of the following for every firmware image you ship to those devices.

**Option 1 — KMU defaults with ITS fallback (recommended for v1.0.1+ field updates):**

Use the normal nRF54L KMU migration settings and leave the :kconfig:option:`CONFIG_CHIP_CRYPTO_PSA_DAC_PRIV_KEY_FALLBACK` Kconfig option set to ``y`` (default).
Commissioning and device attestation keep working because the stack detects the legacy ITS copy at boot and uses it for signing while logging a warning.
Plan re-provisioning when you want the key stored in KMU only.

**Option 2 — Explicit ITS backend:**

Keep the migration destination aligned with the key location:

.. code-block:: kconfig

   CONFIG_CHIP_CRYPTO_PSA_DAC_PRIV_KEY_ITS=y
   # CONFIG_CHIP_CRYPTO_PSA_DAC_PRIV_KEY_KMU is not set

Add this to the :file:`prj.conf` file or a board overlay and verify it in the merged :file:`.config` file after building.

**Do not perform the following operations:**

* Disable the :kconfig:option:`CONFIG_CHIP_CRYPTO_PSA_DAC_PRIV_KEY_FALLBACK` Kconfig option on the KMU-default v1.0.1 firmware for these units because boot stops when the ITS copy is found, until the ITS copy is removed or the device is re-provisioned.

* Perform a factory reset on firmware that erases settings (:kconfig:option:`CONFIG_CHIP_FACTORY_RESET_ERASE_SETTINGS`) while the DAC key is stored only in ITS and you have not yet updated to the firmware with the fallback.
  If the key was in ITS and a different backend is selected, the factory reset erases the ITS copy and the DAC private key is permanently lost.
  The device can no longer pass device attestation until it is re-provisioned with new factory data, and updating the firmware afterwards does not restore the key.
  Update the firmware first, and re-provision the device before you rely on a factory reset.

Path C — New development on v1.0.1+
-----------------------------------

No Kconfig changes are required for new nRF54L Series devices that will boot v1.0.1 first.
KMU remains the default when :kconfig:option:`CONFIG_CRACEN_LIB_KMU` is available.
See :ref:`matter_platforms_security_dac_priv_key` for backend options.

Recommended validation
======================

After changing the DAC storage settings or migration firmware on the nRF54L Series hardware, complete the following steps:

1. Build and inspect the :file:`build/<app>/zephyr/.config` file for the expected ``CONFIG_CHIP_CRYPTO_PSA_DAC_PRIV_KEY_*`` symbol.
#. On a test device, run through factory reset (if applicable) and full Matter commissioning, including device attestation.
#. When migrating from older |NCS| Matter releases, include commissioning after SMP or Matter OTA in your release test plan (not only the DFU step).
