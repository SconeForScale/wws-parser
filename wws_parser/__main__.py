import re
from dataclasses import dataclass
import pprint
from pymongo import MongoClient
import json
skills = []
assets = []
complications = []

p_attr = re.compile(r"^\s+([(WIL|AGI|STR|VIT|INT|ALT)\/]+)$")


class MultiToggle:
    toggles: list = []

    def get(self):
        for toggle in self.toggles:
            if toggle["val"]:
                return toggle["name"]
        return None

    def set(self, toggle_name: str):
        found_toggle = False

        for toggle in self.toggles:
            if toggle["name"] == toggle_name:
                toggle["val"] = True
                found_toggle = True
            else:
                toggle["val"] = False

        if not found_toggle:
            self.toggles.append({"name": toggle_name, "val": True})

    def clear(self):
        self.toggles = []


def main():
    parse_skills()
    # parse_assets()

    printer = pprint.PrettyPrinter(indent=2)
    printer.pprint(skills)
    with open("skills.json", "w") as outf:
        json.dump(skills, outf)
    # insert_skills()


def parse_assets():
    with open("wayward.txt") as inf:
        asset_toggles = MultiToggle()
        in_assets = False
        previous_line = ""
        for line in inf:
            # these are more like search toggles than "in" toggles
            if line.strip() == "Combat (Accuracy)":
                in_assets = True
                asset_toggles.set("in_asset_name")
                continue
            if not in_assets:
                continue
            print(line)
            # sigh
            try:
                int(line.strip())
                assets.append({"name": previous_line.strip()})
                asset_toggles.set("in_asset_cost")
            except:
                pass
            previous_line = line

            if assets and (
                assets[-1].get("flavor") and (not line.strip().startswith("-"))
            ):
                # if at least one flavor line and no quote attr, we're done
                asset_toggles.set("in_asset_desc")

            if asset_toggles.get() == "in_asset_name":
                if not assets:
                    assets.append({})
                assets[-1]["name"] = line.strip()
                asset_toggles.set("in_asset_cost")
                continue
            elif asset_toggles.get() == "in_asset_cost":
                assets[-1]["cost"] = int(line.strip())
                asset_toggles.set("in_asset_flavor")
                continue
            elif asset_toggles.get() == "in_asset_flavor":
                assets[-1]["flavor"] = assets[-1].get("flavor", "") + line.strip()
                continue
            elif asset_toggles.get() == "in_asset_desc":
                if not line.strip():
                    continue
                assets[-1]["desc"] = (
                    assets[-1].get("description", "") + f"{line.strip()}\n"
                )
                continue


def parse_skills():
    # single pass to determine skill names
    file_line_idx = 0
    with open("wayward.txt") as inf:
        previous_line = None
        for line in inf:
            line = line.rstrip()
            m_attr = p_attr.match(line)
            if (
                m_attr
                and (line.strip() not in ["N/A", "L"])
                and (previous_line.strip() not in ["1h"])
            ):
                skills.append(
                    {
                        "name": previous_line.strip(),
                        "file_line_idx": file_line_idx,
                        "attrs": m_attr.group(1).split("/"),
                        "description": "",
                        "counter": "",
                        "tags": [],
                        "rolls": [],
                        "actions": [],
                    }
                )
            previous_line = line
            file_line_idx += 1

    # big pass to populate skill data, now that we know the start lines
    p_roll = re.compile(r"^D\d+$")
    with open("wayward.txt") as inf:
        skill_toggles = MultiToggle()
        action_toggles = MultiToggle()
        skill_idx = None
        action_idx = None
        file_line_idx = 0
        for line in inf:
            found_skill_name = False
            for idx, skill in enumerate(skills):
                if file_line_idx == skill["file_line_idx"]:
                    skill_idx = idx
                    found_skill_name = True
                    break
            file_line_idx += 1
            if skill_idx is None:
                # skip lines until the first skill
                continue
            if found_skill_name:
                # skip attrs line
                skill_toggles.set("in_skill_desc")
                continue

            # line trigger handling
            if line.strip() == "Countered By":
                skill_toggles.set("in_skill_counter")
            elif line.strip() == "Tags":
                skill_toggles.set("in_skill_tags")
            elif p_roll.match(line.strip()):
                skills[skill_idx]["rolls"].append(
                    {"val": line.strip(), "description": ""}
                )
                skill_toggles.set("in_roll_desc_1")
                continue
            elif line.strip() == "Skill Actions and Activities":
                skill_toggles.set("in_actions")
                action_toggles.set("in_action_name")
                continue

            # skill handling
            if skill_toggles.get() == "in_skill_desc":
                skills[skill_idx]["description"] += line.strip()
                continue
            elif skill_toggles.get() == "in_skill_counter":
                skills[skill_idx]["counter"] = line.strip()
                continue
            elif skill_toggles.get() == "in_roll_desc_1":
                try:
                    skills[skill_idx]["rolls"][0]["description"] = line.strip()
                except:
                    print(f"Bad roll idx on {skills[skill_idx]['name']}")
                skill_toggles.set("in_roll_desc_2")
                continue
            elif skill_toggles.get() == "in_roll_desc_2":
                try:
                    skills[skill_idx]["rolls"][1]["description"] = line.strip()
                except:
                    print(f"Bad roll idx on {skills[skill_idx]['name']}")
                continue

            # nested action handling
            if action_toggles.get() == "in_action_name":
                if line.strip() == "Related Assets:":
                    # done go home no more actions
                    action_toggles.set("no_actions")
                    continue
                skills[skill_idx]["actions"].append(
                    {
                        "name": line.strip(),
                        "ap": "",
                        "dc": "",
                        "counter": "",
                        "trigger": "",
                        "description": "",
                        "tags": [],
                    }
                )
                action_idx = len(skills[skill_idx]["actions"]) - 1
                action_toggles.set("in_action_ap")
                continue
            elif action_toggles.get() == "in_action_ap":
                if line.strip().startswith("AP:"):
                    skills[skill_idx]["actions"][action_idx]["ap"] = (
                        line.strip().split("AP:")[1].strip()
                    )
                else:
                    skills[skill_idx]["actions"][action_idx]["ap"] = line.strip()
                action_toggles.set("in_action_dc")
                continue
            elif action_toggles.get() == "in_action_dc":
                if line.strip().startswith("DC:"):
                    skills[skill_idx]["actions"][action_idx]["dc"] = (
                        line.strip().split("DC:")[1].strip()
                    )
                else:
                    skills[skill_idx]["actions"][action_idx]["dc"] = line.strip()
                action_toggles.set("in_action_counter_or_trigger")
            elif action_toggles.get() == "in_action_counter_or_trigger":
                if line.strip().startswith("Countered By:"):
                    skills[skill_idx]["actions"][action_idx][
                        "counter"
                    ] = line.strip().split("Countered By: ")[1]
                elif line.strip().startswith("Trigger:"):
                    skills[skill_idx]["actions"][action_idx][
                        "trigger"
                    ] = line.strip().split("Trigger: ")[1]
                action_toggles.set("in_action_desc")
            elif action_toggles.get() == "in_action_desc":
                if not line.strip():
                    # skip random empty lines in action descriptions
                    continue
                if line.strip().startswith("Tags:"):
                    # have to handle tags here too, and assets trigger
                    if len(line.strip().split("Tags: ")) > 1:
                        # lmao empty tag lines
                        skills[skill_idx]["actions"][action_idx]["tags"] = (
                            line.strip().split("Tags: ")[1].split(" ")
                        )
                    # TODO no related assets but the trigger would go here
                    action_toggles.set("in_action_name")
                else:
                    skills[skill_idx]["actions"][action_idx][
                        "description"
                    ] += line.strip()


def insert_skills():
    client = MongoClient("mongodb://root:example@localhost:27017")

    db = client.get_database("db")

    db["skills"].insert_many(skills)


if __name__ == "__main__":
    main()
