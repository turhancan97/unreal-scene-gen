import os
import sys
import importlib
import time
import unreal
import random
from datetime import datetime
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import assets
import pose
import utils
import camera
import mesh_actor
import serialize

importlib.invalidate_caches()
importlib.reload(camera)
importlib.reload(utils)
importlib.reload(mesh_actor)
importlib.reload(assets)
importlib.reload(pose)
importlib.reload(serialize)

AX, AY, AZ =  pose.DESERT_POSE
OBJ_PROXIMITY = 500
SAMPLE_RADIUS = 300

OUTPUT_PATH = "C:/Users/woj/unreal_scripts/out/" + datetime.now().strftime('%y%m%d-%H%M%S')

os.makedirs(OUTPUT_PATH)


def sample_obj_pos(objects):
    # sample radius
    ax_center = random.gauss(AX, SAMPLE_RADIUS)
    ay_center = random.gauss(AY, SAMPLE_RADIUS)
    for o in objects:
        try:
            rot = unreal.Rotator(0, 0, random.uniform(0.0, 360.0))
            
            # Sample X, Y positions
            x = random.gauss(ax_center, OBJ_PROXIMITY)
            y = random.gauss(ay_center, OBJ_PROXIMITY)
            
            # Find ground height at this X,Y position using line trace
            ground_z = utils.detect_ground_at_position(x, y, AZ)
            
            # Calculate proper Z position based on object bounds
            # Get how much the object extends below its origin
            object_offset = o.get_ground_offset()
            
            # Place object so its bottom surface touches the ground
            # Add a small safety margin (5 units) to prevent floating
            spawn_z = ground_z - object_offset + 5
            
            print(f"Object {o.actor.get_actor_label()}: ground_z={ground_z:.2f}, offset={object_offset:.2f}, spawn_z={spawn_z:.2f}")
            
            pos = unreal.Vector(x, y, spawn_z)
            o.move_to(pos, rot)
            
        except Exception as e:
            print(f"Error positioning object {o.actor.get_actor_label()}: {e}")
            # Fallback to original positioning method
            pos = unreal.Vector(
                random.gauss(ax_center, OBJ_PROXIMITY), 
                random.gauss(ay_center, OBJ_PROXIMITY),
                random.gauss(AZ, 0)
            )
            o.move_to(pos, rot)

    n = len(objects)
    for i in range(n):
        for j in range(i + 1, n):
            if objects[i].overlaps(objects[j]):
                return False, (ax_center, ay_center)
            if objects[i].distance_to(objects[j]) > 1000:
                return False, (ax_center, ay_center)
    return True, (ax_center, ay_center)


def sample_camera(cam, objects, axy_center):
    # Calculate the average Z position of all objects for better camera positioning
    object_positions = [o.actor.get_actor_location() for o in objects]
    avg_z = sum(pos.z for pos in object_positions) / len(object_positions) if object_positions else AZ
    ax_center, ay_center = axy_center
    camera_pos = unreal.Vector(
        random.uniform(ax_center-2500, ax_center+2500), 
        random.uniform(ay_center-2500, ay_center+2500), 
        random.uniform(avg_z, avg_z+1500)  # Position camera relative to objects, not fixed AZ
    )
    cam.move_to(camera_pos)
    cam.look_at_many([o.actor for o in objects])

    cam_offset_angles = [cam.angle_to(o.actor) for o in objects]

    print(f"offset angles: {cam_offset_angles}")

    if max(cam_offset_angles) > min(cam.fov())-5:
        return False
    if max(cam_offset_angles) < 10:
        return False

    return True

def schedule(cam, objects, gap=1.5):
    for i in range(500):
        for j in range(10):
            good, (ax_center, ay_center) = sample_obj_pos(objects)
            print(f"Sampling obj pos iter={j}, good={good}")
            if good:
                break 

        for j in range(15):
            good = sample_camera(cam, objects, (ax_center, ay_center))
            print(f"Sampling camera iter={j}, good={good}")
            if good:
                break 

        cam.take_screenshot(out_name=f"{OUTPUT_PATH}/img_{i:04d}.jpg", delay=0.2) 

        params = serialize.snapshot_params([o.actor for o in objects], cam.actor)
        json.dump(params, open(f"{OUTPUT_PATH}/params_{i:04d}.json","w"), indent=2, ensure_ascii=False)

        t0 = time.time()
        while time.time() - t0 < gap:
            yield None

if __name__ == "__main__":
    utils.destroy_by_tag(tag="SCRIPT_GENERATED")

    cube = mesh_actor.MeshActor(
        assets.CUBE_PATH, 
        label="Cube", 
        scale=unreal.Vector(1,1,2)
    ).set_material(assets.BASIC_MTL_PATH)

    rock = mesh_actor.MeshActor(assets.ROCK_PATH, label="Rock")
    truck = mesh_actor.MeshActor(assets.TRUCK_PATH, label="Truck")
    
    cam = camera.RenderCineCamera(label="RenderCamera")
    
    pt = utils.PyTick()
    pt.schedule.append(schedule(cam, [cube, rock, truck]))

