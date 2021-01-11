import os
import bpy
import enum
import argparse

class MeshFormat(Enum):
    fbx = 'fbx'
    obj = 'obj'
    nif = 'nif'

    def __str__(self):
        return self.value

class TextureFormat(Enum):
    bmp = 'bmp'
    dds = 'dds'
    tga = 'tga'

    def __str__(self):
        return self.value

parser = argparse.ArgumentParser(description='Convert Morrowind asset files.')
parser.add_argument('--asset-path', type=str, required=True,
                    help='Path to your extracted game asset files')
parser.add_argument('--mesh-format', type=MeshFormat, choices=list(MeshFormat),
                    required=True, help='Format to use for processed meshes')
parser.add_argument('--texture-format', type=TextureFormat, choices=list(TextureFormat),
                    required=True, help='Format to use for processed textures')

def main():
    args = parser.parse_args()
    for root, dirs, files in os.walk(args.asset_path):
      for f in files:
        if f.endswith('.nif'):
          in_file = os.path.join(root, f)
          out_file = os.path.join(root, os.path.splitext(f)[0] + '.' + str(args.mesh_format))

          if bpy.context.object:
              bpy.ops.object.mode_set(mode='OBJECT')
          bpy.ops.object.select_all(action='SELECT')
          bpy.ops.object.delete()
          for block in bpy.data.meshes:
                bpy.data.meshes.remove(block)

          for block in bpy.data.materials:
                bpy.data.materials.remove(block)

          for block in bpy.data.textures:
                bpy.data.textures.remove(block)

          for block in bpy.data.images:
                bpy.data.images.remove(block)

          for block in bpy.data.node_groups:
                bpy.data.node_groups.remove(block)
          try:
            print("Converting {}...".format(in_file))
            bpy.ops.import_scene.mw(filepath=in_file)
            bpy.ops.object.select_all(action='DESELECT')

            if any(obj for obj in bpy.data.objects if obj.name.startswith('Tri Tri Tri')):
                print('Mesh with invalid start node found: {}', f)

                rootTri = next((obj for obj in bpy.data.objects if obj.name.startswith('Tri Ex')), None)
                incorrectRootTri = rootTri.children[0]
                sceneRoot = next((obj for obj in bpy.data.objects if obj.name.startswith('Ex')), None)

                # ~ print('current rootTri: {}:', rootTri)
                # ~ print('incorrect rootTri: {}:', incorrectRootTri)
                # ~ print('sceneRoot: {}', sceneRoot)

                for obj in incorrectRootTri.children:
                    obj.parent = rootTri

                bpy.ops.object.select_all(action='DESELECT')
                incorrectRootTri.select_set(True)
                bpy.ops.object.delete()

                print('Attempting to merge meshes')
                for obj in bpy.data.objects:
                    if obj.name.startswith('Tri'):
                        obj.select_set(True)
                        if obj.name.endswith('0'):
                            bpy.context.view_layer.objects.active = obj

                bpy.ops.object.join()

                print('Attempting to merge textures')
                bpy.ops.object.select_all(action='DESELECT')
                bpy.context.scene.render.engine = 'CYCLES'

                rootTri = next((obj for obj in bpy.data.objects if obj.name.startswith('Tri Ex')), None)
                print('rootTri: {}', rootTri)
                print('rootTri Type: {}', rootTri.type)

                if (rootTri.type != 'MESH'):
                    rootTri = rootTri.children[0]
                rootTri.select_set(True)
                rootTri.data.uv_layers.new(name='new')
                rootTri.data.uv_layers['new'].active = True

                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.uv.unwrap()

                obj = bpy.context.active_object
                print('Selected: {}', obj.name)
                print('Selected Type: {}', obj.type)

                # You can choose your texture size (This will be the de bake image)
                image_name = obj.name + '_BakedTexture'
                img = bpy.data.images.new(image_name,1024,1024)

                #Due to the presence of any multiple materials, it seems necessary to iterate on all the materials, and assign them a node + the image to bake.
                for mat in obj.data.materials:
                    print('adding node to material: {}', mat.name)
                    mat.use_nodes = True #Here it is assumed that the materials have been created with nodes, otherwise it would not be possible to assign a node for the Bake, so this step is a bit useless
                    nodes = mat.node_tree.nodes
                    texture_node = nodes.new('ShaderNodeTexImage')
                    texture_node.name = 'Bake_node'
                    texture_node.select = True
                    nodes.active = texture_node
                    texture_node.image = img #Assign the image to the node

                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, save_mode='EXTERNAL')

                if args.texture_format == TextureFormat.bmp:
                    img.save_render(filepath=os.path.join(root, os.path.splitext(f)[0] + ".bmp"))
                elif args.texture_format == TextureFormat.dds:
                    img.save_render(filepath=os.path.join(root, os.path.splitext(f)[0] + ".dds"))
                elif args.texture_format == TextureFormat.tga:
                    img.save_render(filepath=os.path.join(root, os.path.splitext(f)[0] + ".tga"))
                else:
                    print("Unrecognized texture format requested: " + str(args.texture_format))

                bpy.ops.object.mode_set(mode='OBJECT')
                #In the last step, we are going to delete the nodes we created earlier
                for mat in obj.data.materials:
                    for n in mat.node_tree.nodes:
                        if True and n.name == 'Bake_node':
                            mat.node_tree.nodes.remove(n)
                    bpy.ops.object.select_all(action='DESELECT')
                    bpy.data.materials.remove(mat)

                newMat = bpy.data.materials.new(os.path.splitext(f)[0])
                bpy.ops.material.mw_create_shader()
                print(dir(newMat))


                if args.mesh_format == MeshFormat.nif:
                    bpy.ops.export_scene.mw(filepath=out_file)
                elif args.mesh_format == MeshFormat.fbx:
                    bpy.ops.export_scene.fbx(filepath=out_file)
                elif args.mesh_format == MeshFormat.obj:
                    bpy.ops.export_scene.obj(filepath=out_file)
                else:
                    print("Unrecognized mesh format requested: " + str(args.mesh_format))

          except Exception as e:
            print("Corrupted NIF file: {}".format(in_file))
            print(e)

if __name__ == "__main__":
    main()
