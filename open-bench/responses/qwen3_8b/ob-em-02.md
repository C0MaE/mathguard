To determine the time it takes for a capacitor to discharge to half its initial voltage through a resistor, we use the exponential decay formula for an RC circuit:

$$
V(t) = V_0 e^{-t/(RC)}
$$

We are given:
- Capacitance $ C = 47\,\mathrm{\mu F} = 47 \times 10^{-6}\,\mathrm{F} $
- Resistance $ R = 10\,\mathrm{k\Omega} = 10 \times 10^3\,\mathrm{\Omega} $

We are asked to find the time $ t $ when the voltage drops to half its initial value, i.e., $ V(t) = \frac{V_0}{2} $. Substituting into the equation:

$$
\frac{V_0}{2} = V_0 e^{-t/(RC)}
$$

Divide both sides by $ V_0 $:

$$
\frac{1}{2} = e^{-t/(RC)}
$$

Take the natural logarithm of both sides:

$$
\ln\left(\frac{1}{2}\right) = -\frac{t}{RC}
$$

$$
-\ln(2) = -\frac{t}{RC}
$$

$$
t = RC \ln(2)
$$

Now compute the numerical value:

$$
RC = 10 \times 10^3 \times 47 \times 10^{-6} = 0.47\,\mathrm{s}
$$

$$
t = 0.47 \times \ln(2) \approx 0.47 \times 0.693147 \approx 0.3258\,\mathrm{s}
$$

Rounding to three decimal places:

$$
t \approx 0.326\,\mathrm{s}
$$

---

RESULT  
t [time until half the initial voltage] = $ RC \ln(2) $ = $ 0.326 $ s
