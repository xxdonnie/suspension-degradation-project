# Sensor Placement

## Placement philosophy

The strain gauge and accelerometer are placed to capture the maximum relevant signal with the least distortion, subject to physical constraints (adhesive mounting only, no permanent modifications, cable routing that does not interfere with suspension travel).

---

## Strain gauge — location and orientation

**Target location:** The outer face of the damper tube, at or immediately below the spring seat weld, on the side facing away from the vehicle centerline (tension side during lateral load events from the spring eccentricity).

**Rationale:** The spring seat weld region experiences the highest combined stress under bump loading: axial compression from the road force, plus bending from the eccentrically applied spring load. Stress analysis of idealized MacPherson struts (tube under combined axial + bending) shows maximum surface bending stress at the spring seat elevation, on the side in tension relative to the bending axis. Placing the gauge here maximises signal amplitude and places it at the location most relevant to fatigue crack initiation.

**Gauge axis orientation:** The gauge grid is aligned parallel to the tube axis (longitudinal direction). Under axial + bending load, the dominant principal stress is axial on the tube surface. A longitudinally oriented gauge captures both the axial compression and the surface bending stress, giving the highest output for the expected load combination.

**Mounting surface preparation:**
1. Degrease the tube surface with isopropyl alcohol
2. Lightly abrade with 400-grit wet/dry paper to remove surface oxidation
3. Re-degrease and dry
4. Apply gauge using cyanoacrylate (CA) adhesive with finger pressure for 60 seconds
5. Allow 24 hours cure before exposing to vibration

CA adhesive is adequate for the operating temperature range (−10°C to +80°C in a wheel arch environment) and provides a rigid bond that minimises gauge installation strain error.

**Cable routing:** The lead wires are dressed along the damper tube with self-amalgamating tape at 50 mm intervals, avoiding contact with the coil spring. Slack is left at the upper mount (approximately 100 mm extra loop) to accommodate damper travel without putting tension on the solder joints. The cable exits into the engine bay through an existing grommeted aperture.

---

## Accelerometer — location and orientation

**Target location:** The upper spring mount area (strut tower, body side), or directly on the upper mount housing if access allows.

**Rationale:** Two possible placements were considered:

1. **Wheel hub / knuckle area:** Captures the raw road input before suspension filtering. Maximises signal amplitude and contains the most information about road surface. However, this location is in the rotating/articulating suspension, making cable routing and mounting difficult and increasing the risk of cable damage.

2. **Upper mount area (strut tower):** Captures the force transmitted through the damper to the body after suspension attenuation. Easier to mount and route cables, lower vibration environment. The signal is attenuated relative to the wheel input, particularly above the damper natural frequency, but body-side acceleration is sufficient to characterise the loading spectrum for this project.

**Decision:** Upper mount area, strut tower top panel (body side). This location is accessible without wheel removal, allows a clean adhesive mount to the sheet metal, and keeps cables entirely within the engine bay.

**Orientation:** The MPU-6050 is mounted with its z-axis vertical (perpendicular to the road, positive upward). This aligns the primary fatigue-loading direction with the highest-sensitivity axis. The x-axis points forward (longitudinal) and y-axis points toward the wheel (lateral). The exact mounting angle relative to vertical is noted for each session as it may vary slightly if the module is remounted.

**Mounting method:** Double-sided foam tape (high-density, 1 mm thickness) applied to a flat section of the strut tower panel, supplemented with a small cable tie through an existing panel hole to prevent the module from detaching. Foam tape introduces a small amount of compliance at high frequencies but this is acceptable at 200 Hz.

---

## Practical limitations

- The spring seat elevation on the assembled strut is not accessible with the strut in-situ. The gauge was applied with the strut removed from the vehicle and reinstalled after cure. This means the gauge sees the strut installation torque as a tare load, which is included in `STRAIN_ZERO_OFFSET` if offset calibration is performed.
- Cable routing through the wheel arch requires periodic inspection — self-amalgamating tape can loosen if the surface is wet and dirty. Check cable routing before each test session.
- The accelerometer foam tape mount may shift slightly between sessions. A consistent reference mark on the strut tower is used to verify that the orientation is repeatable. Any orientation change greater than approximately 5° is documented in the session log.
- Both sensors are on the same side of the vehicle (driver's side front, or passenger's side front — to be confirmed at installation and documented). Only one strut is instrumented.
