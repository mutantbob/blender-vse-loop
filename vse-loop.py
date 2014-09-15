bl_info = {
    "name" : "VSE loop media",
    "description": "easily loop the frames of the target strip",
    "author" : "Robert Forsman <blender@thoth.purplefrog.com>",
    "version": (0,1),
    "blender": (2,71,0),
    "location": "Video Sequence Editor > Strip > Loop Media",
    "warning": "",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/Sequencer/Loop_Media",
    "category": "Sequencer",
}


import bpy
from math import ceil

def quote_name(str):
    return '"'+str.replace('"', '\\"').replace('\\', '\\\\')+'"'

class SequencerLoopMedia(bpy.types.Operator):
    """Loop the source strip's frames by creating or adjusting a Speed effect strip with a cyclic fcurve on the speed_factor which has been configured as frame_number instead"""
    bl_idname = "sequencer.loop_media"
    bl_label = "Loop Media"
    bl_options = {'REGISTER', 'UNDO'}


    repeat_count = bpy.props.FloatProperty(name="Repeat Count", default=2.0, min=1.0,
                                      subtype='FACTOR', precision=2, step=5,
                                      description="how many times to repeat the media")

    def execute(self, ctx):
        try:
            SequencerLoopMedia.loop_media_op(ctx.scene, self.repeat_count)
            return {'FINISHED'}
        except ValueError as e:
            self.report({'INFO'}, e.args[0])
            return {'CANCELLED'}
        except AttributeError as e:
            self.report({'INFO'}, e.args[0])
            return {'CANCELLED'}

    @classmethod
    def loop_media_op(cls, scene, repeat_count):
        cls.loop_media(scene.sequence_editor.active_strip, scene, repeat_count)

    @classmethod
    def loop_media(cls, strip, scene, repeat_count):

        speed_control = cls.find_speed_control_for(strip, scene)

#        speed_control.use_default_fade = False
#        speed_control.use_as_speed = False
        # if we set those to the correct value now, the fcurve doesn't obey its cycle.
        # I have no idea why.

        media = speed_control
        while hasattr(media, "input_1"):
            # follow the effects chain to the base media
            media = media.input_1

        # get the fcurve controlling the speed_factor property on the speed_control strip
        fcurve = cls.get_fcurve_for_looper(scene, speed_control)

        # make that fcurve have only 3 points
        kp = fcurve.keyframe_points
        while len(kp) >3:
            kp.delete(kp[-1])
        if len(kp) < 3:
            kp.add(3-len(kp))

        frame_start = media.frame_start
        duration = media.frame_duration
        # set those keyframe points to a sawtooth pattern
        kp[0].co = (frame_start,0)
        kp[0].interpolation = 'LINEAR'
        kp[1].co = (frame_start+duration-1,duration-1)
        kp[1].interpolation = 'CONSTANT'
        kp[2].co = (frame_start+duration,0)
        kp[2].interpolation = 'CONSTANT'

        # make sure there's a CYCLES modifier to make the sawtooth repeat indefinitely
        cycles = None
        for mod in fcurve.modifiers:
            if mod.type=='CYCLES':
                cycles = mod
                break

        if cycles is None:
            cycles = fcurve.modifiers.new('CYCLES')

        # adjust the duration of the source media to take advantage of the sawtooth pattern
        media.frame_final_duration = ceil(duration * repeat_count)

        # rig the speed_factor to be interpreted as a frame_number instead.
        speed_control.use_default_fade = False
        speed_control.use_as_speed = False

        # recalculate the effect strip bounds
        speed_control.update()

    @classmethod
    def get_fcurve_for_looper(cls, scene, speed_control):

        if scene.animation_data is None:
            scene.animation_data_create()

        action = scene.animation_data.action
        if action is None:
            action = bpy.data.actions.new(scene.name+"Action")
            scene.animation_data.action = action
        # warning, if there is anything needing quoting in the strip name, it probably won't show up in the
        # fcurves window until blender fixes a bug.
        data_path = "sequence_editor.sequences_all[%s].speed_factor" %quote_name(speed_control.name)
        for fc in action.fcurves:
            if (fc.data_path == data_path):
                return fc

        fc = action.fcurves.new(data_path)
        return fc

    @classmethod
    def find_speed_control_for(cls, other_strip, scene):

        if (other_strip.type == 'SPEED'):
            # the user already picked the speed control
            return other_strip

        # find a speed control pointed at the specified strip
        for strip in scene.sequence_editor.sequences_all:
            if strip.type == 'SPEED' and strip.input_1 == other_strip:
                return strip

        # sigh, we must create one

        # XXX I really wish I knew how to find an uncluttered channel.  It's probably a secret C function inaccessible from python.
        ch = other_strip.channel+1
        s = other_strip.frame_start
        e = s + other_strip.frame_final_duration - 1

        effect = scene.sequence_editor.sequences.new_effect("Loop Media", 'SPEED', ch, s, frame_end=e,
                                                            seq1=other_strip)
        # because somehow setting frame_end in the previous method call accomplishes nothing
        effect.update()

        return effect



#
#

def menu_func(self, ctx):
    self.layout.operator(SequencerLoopMedia.bl_idname, text = SequencerLoopMedia.bl_label)


def register():
    bpy.utils.register_module(__name__)
    bpy.types.SEQUENCER_MT_strip.append(menu_func)

def unregister():
    bpy.types.SEQUENCER_MT_strip.remove(menu_func)
    bpy.utils.unregister_module(__name__)


if __name__ == "__main__":
    try:
        unregister()
    except:
        pass
    register()
