#version 440
// Builds the picture from blocks, from the middle outwards. Every pixel decides alone
// whether its block is shown yet, so any block size costs the same.
//   progress 0..1  radius of the shown area (with a ragged edge)
//   sharp    0..1  blend from the blocky picture into the real one
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float progress;
    float sharp;
    float block;
    vec2 size;
};
layout(binding = 1) uniform sampler2D source;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

void main() {
    vec2 cell = floor(qt_TexCoord0 * size / block);
    vec2 middle = (ceil(size / block) - 1.0) / 2.0;
    float order = length(cell - middle) / length(middle) + hash(cell) * 0.06;
    float shown = step(order, progress * 1.07);
    vec4 blocky = texture(source, clamp((cell + 0.5) * block / size, 0.0, 1.0));
    vec4 color = mix(blocky, texture(source, qt_TexCoord0), sharp);
    // Black where the picture has not arrived yet.
    fragColor = vec4(color.rgb * shown, 1.0) * qt_Opacity;
}
