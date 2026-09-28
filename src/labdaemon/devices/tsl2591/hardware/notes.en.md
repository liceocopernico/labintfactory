## How the lux value is computed

The TSL2591 has two photodiodes. CH0 sees the whole spectrum, visible and infrared; CH1 sees only infrared. The eye does not see infrared, so the lux formula removes it:

lux = (CH0 − CH1) · (1 − CH1/CH0) / CPL, with CPL = t · g / 408

where t is the integration time in ms and g the gain.

## Choosing gain and integration time

A longer integration time or a higher gain gives more counts per lux: finer resolution, but the sensor saturates sooner. Pick settings where the blank reads well below full scale (36 863 counts at 100 ms, 65 535 from 200 ms), and keep the blank and the samples on the same settings.

## Absorbance

The photometer measures how much light gets through the cuvette: T = I / I₀ and A = log₁₀(I₀ / I). The LED colour should match the absorption band of the solution: a blue solution absorbs orange-red light.
