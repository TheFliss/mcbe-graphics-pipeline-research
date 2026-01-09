#
#  Copyright (c) 2026 TheFliss_
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import renderdoc as rd
import os
import re

# MAIN SETTINGS
IN_RANGE = True
START_EVENT = 1000
END_EVENT = 1300

capture_path = pyrenderdoc.GetCaptureFilename()

if not capture_path:
  print("ERROR: No capture file open!")
  exit(1)

capture_filename = os.path.basename(capture_path)
if IN_RANGE:
  save_path = os.path.join(os.path.dirname(capture_path), capture_filename.replace(".", "_") + f"_{START_EVENT}-{END_EVENT}_binary")
else:
  save_path = os.path.join(os.path.dirname(capture_path), capture_filename.replace(".", "_") + "_binary")

if not os.path.exists(save_path):
  os.makedirs(save_path)

shader_stages = []
potential_stages = [
  'Vertex', 'Hull', 'Domain', 'Geometry', 'Pixel', 'Compute',
  'Task', 'Mesh', 'RayGen', 'AnyHit', 'ClosestHit', 
  'Miss', 'Intersection', 'Callable'
]

for stage_name in potential_stages:
  if hasattr(rd.ShaderStage, stage_name):
    shader_stages.append(getattr(rd.ShaderStage, stage_name))

def flatten_actions(action_list, flat_list):
  for action in action_list:
    flat_list.append(action)
    if action.children:
      flatten_actions(action.children, flat_list)

def my_callback(controller):

  all_actions = []
  flatten_actions(controller.GetRootActions(), all_actions)

  if IN_RANGE:
    print(f"Mapping unique shaders in range {START_EVENT}-{END_EVENT}...")
  else:
    print(f"Mapping unique shaders...")

  shader_map = {}

  for action in all_actions:
    if IN_RANGE:
      if action.eventId < START_EVENT: continue
      if action.eventId > END_EVENT: continue
    if not (action.flags & (rd.ActionFlags.Drawcall | rd.ActionFlags.Dispatch)):
      continue

    controller.SetFrameEvent(action.eventId, True)
    state = controller.GetPipelineState()

    for stage in shader_stages:
      refl = state.GetShaderReflection(stage)
      if refl and refl.resourceId != rd.ResourceId.Null():

        if refl.resourceId not in shader_map:

          shader_map[refl.resourceId] = {
            "stage_name": str(stage).split('.')[-1],
            "events": [],
          }

          res_id_str = str(refl.resourceId).split(':')[-1].strip("<> ")

          file_name = f"{res_id_str}.{str(stage).split('.')[-1]}.dxbc"
          with open(os.path.join(save_path, file_name), "wb") as f:
            f.write(refl.rawBytes)
            print("Saving shader bytecode to", file_name)

        if action.eventId not in shader_map[refl.resourceId]["events"]:
          shader_map[refl.resourceId]["events"].append(action.eventId)
          print(f"Added {action.eventId} event")

  print(f"Writing a call table for {len(shader_map)} unique shaders...")

  table_path = os.path.join(save_path, "call_table.txt")
  with open(table_path, "w", encoding="utf-8") as table:
    table.write(f"CALL TABLE FOR {capture_filename}\n")

    for res_id, info in sorted(shader_map.items()):
      res_id_str = str(res_id).split(':')[-1].strip("<> ")

      events_str = ", ".join(map(str, sorted(info["events"])))
      table.write(f"Shader ID: {res_id_str} ({info['stage_name']})\n")
      table.write(f"Used by Events: {events_str}\n")
      table.write("-" * 40 + "\n")

  print(f"Shaders saved to: {save_path}/")

pyrenderdoc.Replay().BlockInvoke(my_callback)
