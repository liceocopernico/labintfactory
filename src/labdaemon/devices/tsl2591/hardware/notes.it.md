## Come si calcola il valore in lux

Il TSL2591 ha due fotodiodi. CH0 vede tutto lo spettro, visibile e infrarosso; CH1 vede solo l'infrarosso. L'occhio non vede l'infrarosso, quindi la formula dei lux lo toglie:

lux = (CH0 − CH1) · (1 − CH1/CH0) / CPL, con CPL = t · g / 408

dove t è il tempo di integrazione in ms e g il guadagno.

## Scegliere guadagno e tempo di integrazione

Un tempo di integrazione più lungo o un guadagno più alto danno più conteggi per lux: risoluzione più fine, ma il sensore satura prima. Scegli impostazioni con cui il bianco resta ben sotto il fondo scala (36 863 conteggi a 100 ms, 65 535 da 200 ms) e usa le stesse impostazioni per il bianco e per i campioni.

## Assorbanza

Il fotometro misura quanta luce attraversa la cuvetta: T = I / I₀ e A = log₁₀(I₀ / I). Il colore del LED deve corrispondere alla banda di assorbimento della soluzione: una soluzione blu assorbe la luce arancione-rossa.
