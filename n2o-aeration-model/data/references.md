# References used in the v1 model

This repository is **not** a calibrated plant model. It is a simplified, literature-guided MVP intended to reproduce the qualitative role of aeration strategy on N2O behavior in secondary treatment.

## Main sources

1. **Kemmou, L., & Amanatidou, E. (2023).**
   *Factors Affecting Nitrous Oxide Emissions from Activated Sludge Wastewater Treatment Plants—A Review.*
   Resources, 12(10), 114.
   DOI: 10.3390/resources12100114

   Used here for the high-level process logic that identifies DO, nitrite accumulation, rapidly changing conditions, COD/N, pH, and temperature as major N2O drivers in activated sludge systems.

2. **Duan, H., van den Akker, B., Thwaites, B. J., Peng, L., Herman, C., Pan, Y., Ni, B.-J., Watt, S., Yuan, Z., & Ye, L. (2020).**
   *Mitigating nitrous oxide emissions at a full-scale wastewater treatment plant.*
   Water Research, 185, 116196.
   DOI: 10.1016/j.watres.2020.116196

   Used here to motivate the repository focus on aeration strategy, the trade-off between N2O mitigation and aeration cost, and the value of dynamic DO control.

3. **Peng, L., Ni, B.-J., Erler, D., Ye, L., & Yuan, Z. (2014).**
   *The effect of dissolved oxygen on N2O production by ammonia-oxidizing bacteria in an enriched nitrifying sludge.*
   Water Research, 66, 12-21.
   DOI: 10.1016/j.watres.2014.08.009

   Used here to justify making AOB-linked N2O production depend on DO and to include distinct low-DO and oxygenated AOB-linked N2O surrogate pathways.

4. **Law, Y., Lant, P., & Yuan, Z. (2013).**
   *The Confounding Effect of Nitrite on N2O Production by an Enriched Ammonia-Oxidizing Culture.*
   Environmental Science & Technology, 47(13), 7186-7194.
   DOI: 10.1021/es4009689

   Used here to justify making AOB-linked N2O production increase with nitrite availability.

5. **Massara, T. M., Solís, B., Guisasola, A., Katsou, E., & Baeza, J. A. (2018).**
   *Development of an ASM2d-N2O model to describe nitrous oxide emissions in municipal WWTPs under dynamic conditions.*
   Chemical Engineering Journal, 335, 185-196.
   DOI: 10.1016/j.cej.2017.10.119

   Used here as architectural inspiration for separating biological kinetics, dynamic conditions, and N2O pathways in a modular way.

6. **Pocquet, M., Wu, Z., Queinnec, I., & Spérandio, M. (2016).**
   *A two pathway model for N2O emissions by ammonium oxidizing bacteria supported by the NO/N2O variation.*
   Water Research, 88, 948-959.
   DOI: 10.1016/j.watres.2015.11.029

   Used here as further support for representing AOB N2O formation with two surrogate pathways in an extensible modeling framework.

## What is literature-guided vs assumed?

### Literature-guided in v1
- DO as a dominant control variable for N2O behavior
- Nitrite-enhanced AOB-linked N2O production
- Separate AOB-linked and heterotrophic contributions to N2O
- Heterotrophic denitrification acting as both N2O source and N2O sink
- Gas stripping during aeration
- Trade-off between N2O mitigation and aeration effort / energy proxy

### Simplifying assumptions in v1
- One equivalent reactor instead of a full multi-zone plant
- Lumped COD state rather than a full ASM COD fractionation
- Static pH input rather than full alkalinity and acid-base chemistry
- Simple proportional aeration controller rather than plant blower logic
- Aeration energy represented as a proxy proportional to oxygen transfer effort
- Nominal parameter values chosen for stable qualitative behavior, not calibration
