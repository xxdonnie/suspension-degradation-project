# Vehicle and Strut Description

## Test Vehicle

| Parameter | Value |
|---|---|
| Make / Model | Mitsubishi Space Star (European market) |
| Model year | 2019 |
| Market spec | Germany |
| Engine | 1.2L 3-cylinder MIVEC, 71 PS |
| Kerb weight | ~870 kg (manufacturer figure) |
| Front suspension | MacPherson strut with lower control arm |
| Rear suspension | Torsion beam axle |
| Tyres (front) | 175/60 R15 (standard fit) |
| Condition at start | New OEM struts, odometer reading recorded at installation |

The Space Star is a B-segment city car with a conventional front MacPherson strut layout. It was selected because the suspension geometry is simple enough to model in FEM without excessive geometric idealization, the components are inexpensive to replace, and the vehicle is driven daily under varied but roughly repeatable conditions.

---

## MacPherson Strut Architecture

A MacPherson strut combines the spring, damper, and suspension upright into a single load-bearing unit. The key structural elements are:

```
      Upper mount (rubber-bonded bearing)
           │
    ┌──────┴──────┐
    │  Coil spring │   ← loads the spring seat weld on rebound
    │             │
    ├─ Spring seat ┤   ← welded to outer damper tube; primary fatigue site
    │             │
    │  Damper tube │   ← outer tube (static), inner rod (dynamic)
    │             │
    └──────┬──────┘
           │
    Steering knuckle (pinch-clamped to strut base)
           │
    Lower ball joint → lower control arm
```

**Upper mount:** Rubber-bonded metal bearing pressed into the strut tower. Allows the strut to rotate during steering without transmitting the full steering torque to the spring. The rubber element provides vibration isolation and introduces compliance that is not modelled in the FEM.

**Coil spring:** Wound steel spring with a manufacturer-specified rate (value not publicly available for this model). Contacts the spring seat at the lower end and a rubber isolator at the top. Under full jounce, coil binding is possible if the strut is near the end of its travel.

**Spring seat weld:** A pressed-steel bracket welded to the outer damper tube at approximately mid-height. This is the highest-stress region of the strut body under combined axial and bending loads. The weld toe concentrates stress and is the most common fatigue crack initiation site on MacPherson struts in service. See `02_physical_system/failure_modes.md`.

**Damper tube and rod:** The outer tube is clamped to the steering knuckle and moves with the wheel. The inner piston rod is anchored at the upper mount. Hydraulic damping force from the piston valve stack is not instrumented or modelled in this project.

**Knuckle connection:** The strut base is clamped into a split bore on the steering knuckle with a pinch bolt. This joint is treated as a fixed boundary condition in the FEM — no rotation or translation at this interface.

---

## Load Paths

During a typical road bump event:

1. Tyre contacts obstacle → vertical force transmitted upward through the knuckle
2. Knuckle loads the strut base — primarily axial compression plus bending from the lateral offset of the contact patch
3. Axial load travels up the damper tube; bending moment increases toward the spring seat
4. Coil spring transmits load through the spring seat into the tube; spring eccentricity adds a lateral force at the seat
5. Combined axial + bending + lateral reaches its peak at the spring seat region
6. Load continues to the upper mount, which absorbs and partially isolates the remainder into the body

The strain gauge is mounted near the spring seat to capture the combined stress state at this location. The accelerometer captures the vertical input at the wheel. See `03_instrumentation/sensor_placement.md`.

---

## Key Dimensions (estimated)

Manufacturer drawings are not publicly available. The values below are estimated from visual inspection and comparison with similar B-segment vehicles. They are adequate for a simplified FEM geometry but carry uncertainty of approximately ±10%.

| Dimension | Estimated value |
|---|---|
| Strut assembly height (knuckle to upper mount) | ~430 mm |
| Outer damper tube outer diameter | ~50 mm |
| Outer damper tube wall thickness | ~3–4 mm |
| Spring free length | ~290 mm |
| Spring wire diameter | ~11 mm |
| Spring coil outer diameter | ~130 mm |
| Distance: knuckle centre to spring seat | ~200 mm |
| Distance: spring seat to upper mount | ~230 mm |

---

## Reference condition

All initial measurements were taken with newly installed OEM replacement struts. The odometer reading at strut installation was recorded and is the baseline for any future degradation comparison. The vehicle was driven by a single person (driver only) for all reference condition sessions.
