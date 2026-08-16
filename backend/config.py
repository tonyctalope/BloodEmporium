import json
import os
from shutil import copyfile
from typing import Dict, List, Any

from exceptions import ConfigError

migrations = [
    # 7.3.3 hawkins reinstatement
    ("iconPerks_situationalAwareness_survivor", "iconPerks_betterTogether_survivor"),
    ("iconPerks_survivalInstincts_survivor",    "iconPerks_innerStrength_survivor"),
    ("iconPerks_guardian_survivor",             "iconPerks_babySitter_survivor"),
    ("iconPerks_pushThroughIt_survivor",        "iconPerks_secondWind_survivor"),

    # 7.5.0 hillbilly changes
    ("iconAddon_junkyardAirFilter_hillbilly",   "iconAddon_greasedThrottle_hillbilly"),
    ("iconAddon_heavyClutch_hillbilly",         "iconAddon_counterweight_hillbilly"),
    ("iconAddon_speedLimiter_hillbilly",        "iconAddon_crackedPrimerBulb_hillbilly"),
    ("iconAddon_puncturedMuffler_hillbilly",    "iconAddon_thermalCasing_hillbilly"),
    ("iconAddon_deathEngravings_hillbilly",     "iconAddon_cloggedIntake_hillbilly"),
    ("iconAddon_bigBuckle_hillbilly",           "iconAddon_chainsBloody_hillbilly"),
    ("iconAddon_mothersHelpers_hillbilly",      "iconAddon_discardedAirFilter_hillbilly"),
    ("iconAddon_leafyMash_hillbilly",           "iconAddon_raggedEngine_hillbilly"),
    ("iconAddon_doomEngravings_hillbilly",      "iconAddon_iridescentEngravings_hillbilly"),
    ("iconAddon_blackGrease_hillbilly",         "iconAddon_theThompsonsMix_hillbilly"),
    ("iconAddon_pighouseGloves_hillbilly",      "iconAddon_highSpeedIdlerScrew_hillbilly"),
    ("iconAddon_iridescentBrick_hillbilly",     "iconAddon_filthySlippers_hillbilly"),

    # 8.1.0 knight changes
    ("iconAddon_ChainmailFragment_knight",      "iconAddon_SharpenedMount_knight"),
    ("iconAddon_LightweightGreaves_knight",     "iconAddon_JailersChimes_knight"),

    # 9.0.0 shroud changes
    ("iconFavors_shroudOfSeparation_killer",    "T_UI_iconsFavors_shroudOfVanishing_killer"),
    ("iconFavors_shroudOfBinding_survivor",     "iconFavors_shroudOfSeparation_survivor"),
]

class Config:
    def __init__(self, validate=False):
        if validate:
            if not os.path.isfile("config.json"):
                copyfile("assets/default_config.json", "config.json")

            with open("config.json", "r") as f:
                self.config: Dict[str, Any] = dict(json.load(f))
            self.commit_changes() # ensure all necessary keys are in (essentially copying missing values)

        with open("config.json", "r") as f:
            self.config = dict(json.load(f))

        # TODO set the value instead of raising error (use get_next_free_profile_name)
        ids = []
        for num, profile in enumerate(self.config["profiles"], 1):
            if "id" not in profile.keys():
                raise ConfigError(f"Missing profile id for profile {num} in config.json")
            if profile["id"] in ids:
                raise ConfigError(f"Multiple profiles with same id (profile {num}) in config.json")
            if "notes" not in profile.keys():
                profile["notes"] = ""

            ids.append(profile["id"])
            invalid_unlockables = []
            for unique_id, v in profile.items():
                # TODO validate that unique_id is a valid unlockable id
                if unique_id not in ["id", "notes"]:
                    if "tier" not in v:
                        invalid_unlockables.append(unique_id)
                        continue
                    if "subtier" not in v:
                        invalid_unlockables.append(unique_id)
                        continue

            [profile.pop(invalid_unlockable) for invalid_unlockable in invalid_unlockables]

        self.bundled_profiles = []
        if os.path.isdir("assets/presets"):
            for file in os.listdir("assets/presets"):
                with open(f"assets/presets/{file}", "r") as f:
                    self.bundled_profiles.append(json.load(f))

    def top_left(self):
        return self.config["capture"]["top_left_x"], self.config["capture"]["top_left_y"]

    def path(self):
        return self.config["path"]

    def hotkey(self):
        return [key for key in self.config["hotkey"].split(" ") if key != ""]

    def interaction(self):
        return self.config["interaction"]

    def primary_mouse(self):
        return self.config["primary_mouse"]

    def node_click_slots(self):
        """
        :return: list of (angle, ring, (horizontal %, vertical %))

        Some bloodweb slots have an in-game hitbox that does not cover the centre of the icon sitting in them
        (bugreport.deadbydaylight.com/projects/pr-5642738318/issues/1913). Which slot misbehaves has nothing to
        do with which unlockable happens to land there - that changes every bloodweb - so a slot is named by
        where it sits: its angle in degrees clockwise from straight up, and its distance from the centre of the
        bloodweb in multiples of the innermost ring's radius. Both are independent of screen resolution.
        """
        slots = []
        for entry in self.config.get("node_click_slots", []):
            try:
                angle, ring, x, y = entry
                slots.append((float(angle), float(ring), (float(x), float(y))))
            except (TypeError, ValueError):
                continue # malformed entry: click the centre rather than refuse to run
        return slots

    def node_click_offsets(self):
        """
        :return: unlockable (in-game name or unique id, lower case) -> (horizontal %, vertical %), taking
                 precedence over node_click_slots for that unlockable

        Not surfaced in the app, since the hitbox problem is per slot rather than per unlockable. Kept for
        hand-editing config.json if one particular unlockable ever needs its own treatment.
        """
        offsets = {}
        for unlockable, offset in self.config.get("node_click_offsets", {}).items():
            try:
                x, y = offset
                offsets[str(unlockable).strip().lower()] = (float(x), float(y))
            except (TypeError, ValueError):
                continue # malformed entry: fall back to clicking the centre rather than refusing to run
        return offsets

    MAX_NODE_CLICK_OFFSET = 40 # beyond this the click leaves the icon entirely

    @staticmethod
    def parse_node_click_slots(text):
        """
        Parses the settings page text: one "angle, ring, horizontal %, vertical %" entry per line.

        :raise ValueError: with a message meant to be shown to the user
        """
        slots = []
        for num, line in enumerate(text.splitlines(), 1):
            if line.strip() == "":
                continue
            fields = [field.strip() for field in line.split(",")]
            if len(fields) != 4:
                raise ValueError(f"Node click offset line {num} must be "
                                 f"\"angle, ring, horizontal %, vertical %\".")
            try:
                angle, ring, x, y = [float(field) for field in fields]
            except ValueError:
                raise ValueError(f"Node click offset line {num} must be four numbers.")
            if not -360 <= angle <= 360:
                raise ValueError(f"Node click offset line {num}: angle must be between -360 and 360.")
            if ring <= 0:
                raise ValueError(f"Node click offset line {num}: ring must be greater than 0.")
            if max(abs(x), abs(y)) > Config.MAX_NODE_CLICK_OFFSET:
                raise ValueError(f"Node click offset line {num} must stay within "
                                 f"±{Config.MAX_NODE_CLICK_OFFSET}% of the icon.")
            slots.append((angle, ring, (x, y)))
        return slots

    @staticmethod
    def format_node_click_slots(slots):
        return "\n".join(f"{angle:g}, {ring:g}, {x:g}, {y:g}" for angle, ring, (x, y) in slots)

    def set_node_click_slots(self, slots):
        self.config["node_click_slots"] = [[angle, ring, x, y] for angle, ring, (x, y) in slots]
        self.commit_changes()

    @staticmethod
    def parse_node_click_offsets(text):
        """
        Parses the settings page text: one "unlockable, horizontal %, vertical %" entry per line.

        :raise ValueError: with a message meant to be shown to the user
        """
        offsets = {}
        for num, line in enumerate(text.splitlines(), 1):
            if line.strip() == "":
                continue
            fields = [field.strip() for field in line.split(",")]
            if len(fields) != 3:
                raise ValueError(f"Node click offset line {num} must be "
                                 f"\"unlockable, horizontal %, vertical %\".")
            unlockable, x, y = fields
            if unlockable == "":
                raise ValueError(f"Node click offset line {num} is missing an unlockable name or id.")
            try:
                x, y = float(x), float(y)
            except ValueError:
                raise ValueError(f"Node click offset line {num} must end in two numeric percentages.")
            if max(abs(x), abs(y)) > Config.MAX_NODE_CLICK_OFFSET:
                raise ValueError(f"Node click offset line {num} must stay within "
                                 f"±{Config.MAX_NODE_CLICK_OFFSET}% of the icon.")
            offsets[unlockable.lower()] = (x, y)
        return offsets

    @staticmethod
    def format_node_click_offsets(offsets):
        return "\n".join(f"{unlockable}, {x:g}, {y:g}" for unlockable, (x, y) in offsets.items())

    def size(self):
        return self.config["width"], self.config["height"]

    def position(self):
        return self.config["x"], self.config["y"]

    def __profiles(self, bundled=False) -> List[Dict[str, Any]]:
        return self.bundled_profiles if bundled else self.config["profiles"]

    def get_profile_by_id(self, profile_id, bundled=False):
        if profile_id is None:
            return {"id": None, "notes": ""}
        profiles = self.__profiles(bundled)
        return [p for p in profiles if p["id"] == profile_id].pop(0) if len(profiles) > 0 else {"id": None, "notes": ""}

    def notes_by_id(self, profile_id, bundled=False):
        if profile_id is None:
            return ""
        return self.get_profile_by_id(profile_id, bundled).get("notes", "")

    def preference_by_id(self, unlockable_id, profile_id, bundled=False):
        if profile_id is None:
            return 0, 0
        return Config.preference_by_profile(unlockable_id, self.get_profile_by_id(profile_id, bundled))

    @staticmethod
    def preference_by_profile(unlockable_id, profile_data):
        p = profile_data.get(unlockable_id, {})
        return p.get("tier", 0), p.get("subtier", 0)

    def profile_names(self, bundled=False):
        return [profile["id"] for profile in self.__profiles(bundled)]

    def commit_changes(self):
        with open("assets/default_config.json", "r") as default:
            default_config = dict(json.load(default))
            for profile in self.config.get("profiles", []):
                Config.migrate_profile(profile)
            with open("config.json", "w") as output:
                json.dump({
                    "path": self.config.get("path", default_config["path"]),
                    # an empty hotkey matches nothing at all, so fall back rather than lock the user out
                    "hotkey": self.config.get("hotkey", "").strip() or default_config["hotkey"],
                    "interaction": self.config.get("interaction", default_config["interaction"]),
                    "primary_mouse": self.config.get("primary_mouse", default_config["primary_mouse"]),
                    "node_click_slots": self.config.get("node_click_slots",
                                                        default_config["node_click_slots"]),
                    "node_click_offsets": self.config.get("node_click_offsets",
                                                          default_config["node_click_offsets"]),
                    "width": self.config.get("width", default_config["width"]),
                    "height": self.config.get("height", default_config["height"]),
                    "x": self.config.get("x", default_config["x"]),
                    "y": self.config.get("y", default_config["y"]),
                    "profiles": self.config.get("profiles", default_config["profiles"]),
                }, output, indent=4) # to preserve order
        copyfile("config.json", "config_backup.json")

    @staticmethod
    def verify_tiers(widgets):
        non_integer = []
        for widget in widgets:
            try:
                tier, subtier = widget.getTiers()
                if abs(tier) > 999 or abs(subtier) > 999:
                    non_integer.append(widget.unlockable.name)
            except ValueError:
                non_integer.append(widget.unlockable.name)
        return non_integer

    @staticmethod
    def verify_path(path):
        return os.path.isdir(path)

    def set_path(self, path):
        self.config["path"] = path
        self.commit_changes()

    def set_hotkey(self, hotkey):
        self.config["hotkey"] = " ".join(hotkey)
        self.commit_changes()

    def set_interaction(self, interaction):
        self.config["interaction"] = interaction
        self.commit_changes()

    def set_primary_mouse(self, primary_mouse):
        self.config["primary_mouse"] = primary_mouse
        self.commit_changes()

    def set_node_click_offsets(self, node_click_offsets):
        self.config["node_click_offsets"] = {unlockable: list(offset)
                                             for unlockable, offset in node_click_offsets.items()}
        self.commit_changes()

    def set_size(self, width, height):
        self.config["width"] = width
        self.config["height"] = height
        self.commit_changes()

    def set_position(self, x, y):
        self.config["x"] = x
        self.config["y"] = y
        self.commit_changes()

    def set_profile(self, updated_profile):
        if updated_profile["id"] is None:
            return
        self.config["profiles"][self.config["profiles"].index(self.get_profile_by_id(updated_profile["id"]))] = updated_profile
        self.commit_changes()

    def is_profile(self, profile_id):
        """
        :return: whether the profile existed before already
        """
        return profile_id in [profile["id"] for profile in self.__profiles()]

    def get_next_free_profile_name(self):
        profile_ids = [profile["id"] for profile in self.__profiles()]
        i = 0
        profile_id = "new profile"
        while profile_id in profile_ids:
            i += 1
            profile_id = f"new profile ({i})"
        return profile_id

    def add_profile(self, new_profile, index=None):
        """
        :return: whether the profile existed before already
        """

        existing_profile = None
        for profile in self.__profiles():
            if profile["id"] == new_profile["id"]:
                existing_profile = profile

        if "notes" not in new_profile.keys():
            new_profile["notes"] = ""

        if existing_profile is None:
            if index is None:
                self.config["profiles"].append(new_profile)
            else:
                self.config["profiles"].insert(index, new_profile)
        else:
            self.set_profile(new_profile)

        self.commit_changes()

        return existing_profile is not None

    def delete_profile(self, profile_id):
        to_be_removed = [profile for profile in self.__profiles() if profile["id"] == profile_id].pop(0)
        self.config["profiles"].remove(to_be_removed)
        self.commit_changes()

    def export_profile(self, profile_id, bundled=False):
        if profile_id is None:
            return
        profile = self.get_profile_by_id(profile_id, bundled)
        with open(f"exports/{profile_id}.emp", "w") as file:
            file.write(json.dumps(profile))

    @staticmethod
    def migrate_profile(profile):
        for migration_src, migration_dst in migrations:
            if migration_src in profile:
                profile[migration_dst] = profile[migration_src]
                profile.pop(migration_src)