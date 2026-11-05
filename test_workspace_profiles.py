import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from preferences import BackgroundStore, BrandingStore, UserSettingsStore, USER_DEFAULTS
from workspace_profiles import CONFIG_FILES, DEFAULT_PROFILES, WorkspaceProfiles


class WorkspaceProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        self.profiles = WorkspaceProfiles(self.data)

    def image(self, name, color):
        path = self.root / name
        Image.new("RGB", (20, 30), color).save(path)
        return path

    def test_profiles_roundtrip_all_stores_with_shared_media_library(self):
        records = self.profiles.load()
        snapshots = []
        for index, record in enumerate(records):
            config = self.profiles.prepare(record)
            settings = UserSettingsStore(self.data, config_dir=config)
            background = BackgroundStore(self.data, config_dir=config)
            branding = BrandingStore(self.data, config_dir=config)
            source = self.image(f"image-{index}.png", (index * 100, 20, 100))
            music = self.root / f"music-{index}.wav"
            music.write_bytes(f"audio {index}".encode())
            settings.select_music(music, {**USER_DEFAULTS, "brand": record["name"], "rate": index + 20})
            background.select(source, index + 15)
            for kind in BrandingStore.KINDS:
                branding.select(kind, source)
            snapshots.append((settings.load(), background.load(), branding.load()))
            source.unlink()
            music.unlink()
        self.profiles.save(records)
        reopened = WorkspaceProfiles(self.data)
        for record, snapshot in zip(reopened.load(), snapshots):
            config = reopened.prepare(record)
            stores = (UserSettingsStore(self.data, config_dir=config),
                      BackgroundStore(self.data, config_dir=config),
                      BrandingStore(self.data, config_dir=config))
            self.assertEqual(tuple(store.load() for store in stores), snapshot)
            self.assertEqual(len(stores[1].library()["images"]), 3)
            self.assertEqual(len(stores[2].library()), 3)
            self.assertTrue(Path(snapshot[0]["music"]).is_file())
            self.assertTrue(Path(snapshot[1]["background"]).is_file())
        second = self.data / "profiles" / records[1]["id"]
        BackgroundStore(self.data, config_dir=second).clear(22)
        UserSettingsStore(self.data, config_dir=second).clear_music(USER_DEFAULTS)
        BrandingStore(self.data, config_dir=second).reset("logo_image")
        first = self.data / "profiles" / records[0]["id"]
        self.assertEqual(UserSettingsStore(self.data, config_dir=first).load(), snapshots[0][0])
        self.assertEqual(BackgroundStore(self.data, config_dir=first).load(), snapshots[0][1])
        self.assertEqual(BrandingStore(self.data, config_dir=first).load(), snapshots[0][2])
        self.assertFalse((self.data / "settings.json").exists())

    def test_only_first_profile_migrates_legacy_files_once_without_modifying_them(self):
        source = self.image("legacy.png", "red")
        music = self.root / "legacy.wav"
        music.write_bytes(b"legacy audio")
        UserSettingsStore(self.data).select_music(music, {**USER_DEFAULTS, "rate": 26, "brand": ""})
        BackgroundStore(self.data).select(source, 8)
        BrandingStore(self.data).select("logo_image", source)
        legacy = {filename: (self.data / filename).read_bytes() for filename in CONFIG_FILES
                  if (self.data / filename).exists()}
        records = self.profiles.load()
        configs = [self.profiles.prepare(record) for record in records]
        for filename, content in legacy.items():
            self.assertEqual((configs[0] / filename).read_bytes(), content)
            self.assertEqual((self.data / filename).read_bytes(), content)
        for record, config in zip(records[1:], configs[1:]):
            settings = UserSettingsStore(self.data, config_dir=config).load()
            self.assertEqual(settings["rate"], USER_DEFAULTS["rate"])
            self.assertEqual(settings["brand"], record["name"])
            self.assertEqual(settings["ending_text"], "")
            self.assertEqual(settings["music"], "")
            self.assertEqual(BackgroundStore(self.data, config_dir=config).load()["background"], "")
            self.assertEqual(BrandingStore(self.data, config_dir=config).load()["logo_image"], "")
        UserSettingsStore(self.data).save({**USER_DEFAULTS, "rate": -10})
        self.profiles.prepare(records[0])
        self.assertEqual((configs[0] / "settings.json").read_bytes(), legacy["settings.json"])

    def test_fresh_defaults_and_new_tab_clone_remain_independent(self):
        records = self.profiles.load()
        first = self.profiles.prepare(records[0])
        settings = UserSettingsStore(self.data, config_dir=first)
        self.assertEqual(settings.load()["brand"], "Một chút English")
        self.assertEqual(settings.load()["ending_text"], USER_DEFAULTS["ending_text"])
        settings.save({**USER_DEFAULTS, "rate": 17, "ending_text": "My ending"})
        source = self.image("logo.png", "blue")
        BrandingStore(self.data, config_dir=first).select("ending_image", source)
        extra = self.profiles.new_record(4)
        clone = self.profiles.prepare(extra, source_id=records[0]["id"])
        for filename in CONFIG_FILES:
            self.assertEqual((clone / filename).read_bytes(), (first / filename).read_bytes())
        UserSettingsStore(self.data, config_dir=clone).save({**USER_DEFAULTS, "rate": 30})
        self.assertEqual(settings.load()["rate"], 17)
        self.assertNotEqual(extra["id"], self.profiles.new_record(4)["id"])

    def test_metadata_restores_order_renames_and_open_extras_after_default_closed(self):
        records = self.profiles.load()
        records[0]["name"] = "English của tôi"
        records[2]["name"] = "ASVAB mới"
        extra = self.profiles.new_record(4)
        self.profiles.save([extra, *reversed(records)])
        self.profiles.save([records[1], extra])
        restored = WorkspaceProfiles(self.data).load()
        self.assertEqual(restored, records + [extra])
        self.profiles.save(records)
        self.assertEqual(WorkspaceProfiles(self.data).load(), records)
        self.assertEqual([record["id"] for record in restored[:3]], [item[0] for item in DEFAULT_PROFILES])

    def test_bad_metadata_recovers_defaults_and_rejects_unsafe_ids(self):
        defaults = self.profiles.load()
        self.data.mkdir()
        bad_records = [
            {"version": 1, "tabs": [defaults[0], defaults[0]]},
            {"version": 1, "tabs": [{"id": "../outside", "name": "Bad"}]},
            {"version": 1, "tabs": [{"id": "easy-prep", "name": " "}]},
            {"version": 1, "tabs": [{"id": "easy-prep", "name": "x" * 81}]},
            {"version": 1, "tabs": [{"id": "unknown", "name": "Bad"}]},
            {"version": 1, "tabs": "not a list"},
            {"version": 2, "tabs": defaults},
            [],
        ]
        for data in bad_records:
            with self.subTest(data=data):
                self.profiles.config.write_text(json.dumps(data), encoding="utf-8")
                self.assertEqual(self.profiles.load(), defaults)
                self.assertTrue(self.profiles.warning)
        self.profiles.config.write_text("{broken", encoding="utf-8")
        self.assertEqual(self.profiles.load(), defaults)
        self.assertTrue(self.profiles.warning)
        with self.assertRaises(ValueError):
            self.profiles.prepare({"id": "../outside", "name": "Bad"})
        with self.assertRaises(ValueError):
            self.profiles.prepare(defaults[0], source_id="../outside")
        self.assertFalse((self.root / "outside").exists())

    def test_failed_metadata_save_keeps_previous_tabs(self):
        records = self.profiles.load()
        self.profiles.save(records)
        extra = self.profiles.new_record(4)
        with patch("workspace_profiles.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.profiles.save(records + [extra])
        self.assertEqual(WorkspaceProfiles(self.data).load(), records)
        self.assertEqual(list(self.data.iterdir()), [self.profiles.config])


if __name__ == "__main__":
    unittest.main()
