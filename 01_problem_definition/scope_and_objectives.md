# Scope and Objectives

## Background

Suspension components in passenger vehicles are subject to continuous cyclic loading during normal operation. Over time, this loading causes progressive material degradation — primarily fatigue damage — that reduces the structural integrity and ride performance of the system. Despite being a well understood phenomenon in industry, the gap between what finite element models predict and what real-world measurements show remains significant, particularly for low-cost, consumer-grade vehicles.

A 2019 Mitsubishi Space Star (German market spec), featuring a front MacPherson strut suspension, serves as the test platform for this project. Measurements begin with freshly installed OEM struts at a recorded mileage, establishing a known condition reference state from the outset. The vehicle is instrumented with low-cost sensors to capture dynamic loading data during controlled driving conditions. That data is then processed and compared against a finite element model of the strut assembly to evaluate how well simulation captures real fatigue behaviour.

## Problem Statement

Fatigue-driven suspension degradation is typically assessed either through expensive laboratory testing or purely analytical methods. For an engineer without access to professional test equipment, neither route is practical. This project asks: **can a low-cost instrumentation setup, combined with open-source FEM tools, produce a meaningful comparison between experimental fatigue indicators and simulation predictions?**

## Objectives

### Primary objectives

1. Instrument the front suspension of a 2019 Mitsubishi Space Star to measure dynamic strut loading during real-world driving, with the initial dataset acquired at a documented reference condition (new OEM struts, known mileage).
2. Process the acquired signals to extract fatigue-relevant features: load cycles (rainflow counting), stress amplitude distributions, and power spectral density.
3. Build a finite element model of the MacPherson strut assembly and run static and quasi-dynamic load cases representative of the measured conditions.
4. Compare experimental fatigue indicators with FEM-predicted stress distributions and identify the nature, cause and magnitude of any mismatch.
5. Document all assumptions, simplifications, and limitations with engineering rigor.

### Secondary objectives

- Demonstrate a repeatable, low-cost instrumentation workflow applicable to other, similar structural components.
- Produce clean, well-documented Python code for signal processing that can be reused or extended.
- Reflect honestly on what this approach can and cannot tell us about actual component life.

## Scope

### In scope

- Front suspension only (left or right strut — to be decided based on sensor mounting access)
- Initial dataset acquired with new OEM struts as a known-condition reference, with odometer reading recorded at time of installation
- Driving on public roads under defined, mostly repeatable conditions (see `04_data_collection/driving_conditions.md`)
- Quasi-static and modal FEM analysis of the strut assembly
- Fatigue life estimation using stress-life (S-N) approach, with material data from literature
- Comparison of experimental and FEM stress/load indicators at specific measurement points

### Out of scope

- Rear suspension
- Tyre or wheel dynamics (tyre treated as a force input boundary)
- Full vehicle multi-body dynamics simulation
- Accelerated life testing or physical fatigue cycling of the component
- Replacement or disassembly of suspension parts during the project

## Success Criteria

The project is considered successful if:

- At least two independent signal channels (e.g. acceleration + strain) are acquired cleanly over a repeatable drive route, at a documented reference condition
- The signal processing pipeline produces a cycle amplitude distribution that can be used as a load input to the FEM model
- The FEM model converges on physically reasonable stress fields under the defined load cases
- A quantitative comparison between experimental and simulated fatigue indicators is made, even if the match is poor
- All discrepancies are discussed with reference to known sources of modelling and measurement error

## Relevance to Naval Engineering

While this project focuses on automotive suspension, the underlying engineering disciplines transfer directly to naval and offshore structural applications:

- **Fatigue analysis** is central to hull structural design, particularly in way of high-stress regions such as hatch corners, bracket toes, and machinery foundations
- **Signal processing and cycle counting** are used to derive fatigue loading spectra from strain gauge records on ship structures at sea
- **FEM validation against experiment** is standard practice in classification society approval workflows (DNV, Lloyd's Register, Bureau Veritas)
- **Instrumentation under real operating conditions** mirrors the challenge of structural health monitoring on vessels in service

The methods practised here, even at this small scale, directly reflect the workflow used by structural engineers in the maritime industry.
