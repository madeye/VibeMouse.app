from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestAppDelegateStatusCallback(unittest.TestCase):
    """Verify that VoiceMouseApp receives the status change callback."""

    @patch("vibemouse.macos.app_delegate.NSBundle")
    @patch("vibemouse.macos.app_delegate.NSStatusBar")
    @patch("vibemouse.macos.app_delegate.NSMenu")
    @patch("vibemouse.macos.app_delegate.NSMenuItem")
    @patch("vibemouse.macos.app_delegate.NSImage")
    @patch("vibemouse.macos.app_delegate.load_preferences_into_environ")
    @patch("vibemouse.macos.app_delegate.check_accessibility", return_value=True)
    @patch("vibemouse.macos.app_delegate.check_microphone", return_value="authorized")
    @patch("vibemouse.macos.app_delegate.load_config")
    @patch("vibemouse.app.VoiceMouseApp")
    def test_status_callback_wired_to_app(
        self,
        mock_voice_app_cls: MagicMock,
        mock_load_config: MagicMock,
        mock_check_mic: MagicMock,
        mock_check_ax: MagicMock,
        mock_load_prefs: MagicMock,
        mock_nsimage: MagicMock,
        mock_nsmenuitem: MagicMock,
        mock_nsmenu: MagicMock,
        mock_nsstatusbar: MagicMock,
        mock_nsbundle: MagicMock,
    ) -> None:
        # Set up mocks
        mock_nsbundle.mainBundle.return_value = None

        mock_button = MagicMock()
        mock_status_item = MagicMock()
        mock_status_item.button.return_value = mock_button
        mock_nsstatusbar.systemStatusBar.return_value.statusItemWithLength_.return_value = (
            mock_status_item
        )

        mock_menu = MagicMock()
        mock_nsmenu.alloc.return_value.init.return_value = mock_menu

        separator = MagicMock()
        mock_nsmenuitem.separatorItem.return_value = separator
        mock_nsmenuitem.alloc.return_value.initWithTitle_action_keyEquivalent_.return_value = (
            MagicMock()
        )

        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        mock_app_instance = MagicMock()
        mock_voice_app_cls.return_value = mock_app_instance

        from vibemouse.macos.app_delegate import VibemouseAppDelegate

        # The delegate is an ObjC class; we test the Python layer
        # by directly calling the init logic
        delegate = VibemouseAppDelegate.alloc().init()
        delegate.applicationDidFinishLaunching_(None)

        # Verify VoiceMouseApp was created with on_status_change callback
        mock_voice_app_cls.assert_called_once()
        call_kwargs = mock_voice_app_cls.call_args
        self.assertIn("on_status_change", call_kwargs.kwargs)
        self.assertIsNotNone(call_kwargs.kwargs["on_status_change"])


class TestAppDelegateDeviceSubmenu(unittest.TestCase):
    """Verify that the Input Device submenu is created with delegate set."""

    @patch("vibemouse.macos.app_delegate.NSBundle")
    @patch("vibemouse.macos.app_delegate.NSStatusBar")
    @patch("vibemouse.macos.app_delegate.NSMenu")
    @patch("vibemouse.macos.app_delegate.NSMenuItem")
    @patch("vibemouse.macos.app_delegate.NSImage")
    def test_device_submenu_created_with_delegate(
        self,
        mock_nsimage: MagicMock,
        mock_nsmenuitem: MagicMock,
        mock_nsmenu: MagicMock,
        mock_nsstatusbar: MagicMock,
        mock_nsbundle: MagicMock,
    ) -> None:
        mock_nsbundle.mainBundle.return_value = None

        mock_button = MagicMock()
        mock_status_item = MagicMock()
        mock_status_item.button.return_value = mock_button
        mock_nsstatusbar.systemStatusBar.return_value.statusItemWithLength_.return_value = (
            mock_status_item
        )

        mock_main_menu = MagicMock()
        mock_device_submenu = MagicMock()
        mock_nsmenu.alloc.return_value.init.side_effect = [
            mock_main_menu,
            mock_device_submenu,
        ]

        mock_menu_item = MagicMock()
        mock_nsmenuitem.alloc.return_value.initWithTitle_action_keyEquivalent_.return_value = (
            mock_menu_item
        )
        mock_nsmenuitem.separatorItem.return_value = MagicMock()

        from vibemouse.macos.app_delegate import VibemouseAppDelegate

        delegate = VibemouseAppDelegate.alloc().init()
        delegate._status_item = mock_status_item
        delegate._build_menu()

        # The device submenu should have its delegate set to self
        mock_device_submenu.setDelegate_.assert_called_once_with(delegate)
        self.assertIs(delegate._device_submenu, mock_device_submenu)


if __name__ == "__main__":
    unittest.main()
