# Visibility methodology (background)

How looktospace.com computes visibility (public write-up:
https://looktospace.com/methodology). The live computation runs server-side
and the connector uses the site's `/api/v1/visibility` as the single source
of truth. This is background only; the connector never computes tiers.

- `distance_mi`: great-circle distance from the viewer to the launch pad.
- `look_toward`: 16-point compass direction from the viewer toward the point
  where the rocket first rises above the viewer's horizon (the pad's bearing
  when no such point is found). Null when the launch is not visible.
- `lighting`: day / twilight / night, from the sun's elevation at the
  viewer's location at liftoff.
- A representative ascent along the launch azimuth is simulated in 5-second
  steps, with Earth-curvature drop, to find the first horizon clearance, the
  peak elevation and the closest approach (slant range).
- Tier thresholds are on that closest approach (slant range, miles), by
  lighting:

| Tier | Day | Night | Twilight |
|---|---|---|---|
| Excellent | ≤ 90 | ≤ 150 | ≤ 230 |
| Good | ≤ 220 | ≤ 360 | ≤ 600 |
| Fair | ≤ 360 | ≤ 560 | ≤ 1050 |
| Marginal | ≤ 480 | ≤ 780 | ≤ 1600 |

Downgraded one tier if peak elevation < 5°; "Not visible" past the Marginal
limit or if the rocket never climbs 1.5° above the horizon.

When the launch time is only known to the day or coarser
(`time_uncertain: true`), lighting is assumed to be day and the tier is an
estimate that can change once a time is set.

Limits: smooth-Earth model (terrain and buildings ignored), no
light-pollution model, per-mission trajectory variance. Weather and cloud
cover are not part of the tier.
