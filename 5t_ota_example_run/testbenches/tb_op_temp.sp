*******************************************************
* tb_op_params.sp -- Forced Parameter Extraction
*******************************************************
.option post=2      
.option nomod
.option measform=3
.option results
.temp 27


* Universal DUT interface control
.param DUT_HAS_VB2 = 0
.param VB2_DC = 600m
* --- CRITICAL FORMATTING OPTIONS ---
* ingold=2: Forces strict scientific notation (e.g. 1.0e-09), easier for Python.
* numdgt=10: High precision.
* width=5000: Prevents table columns from wrapping to the next line.
.option ingold=2 
.option numdgt=10
.option width=5000 

**************** Parameters ***************************
.param VCM=7.021553e-01
.param dummy_var=0
.include "design_params.sp"

**************** Supplies & Inputs ********************
VSS  vss 0 0
VDD1 vdd 0 VDD
IBIAS vdd ibias DC IBIAS
VVB2 vb2 0 DC 'VB2_DC'
VINP vp 0 DC VCM 
VINN vn 0 DC VCM 

**************** DUT ***************************

.include "dut_wrapper.sp"
* Pin Order: In+, In-, Out, VDD, VSS, Bias, Vbias2
XU1 vp vn vout vdd vss ibias vb2 DUT_UNIVERSAL
CLOAD  vout vss CL

**************** Analysis *****************************
* Dummy sweep to force print output
.dc dummy_var 0 0 1

**************** Operating Point Print ****************
* Note: Ensure all parameters for a device are on one CONTINUOUS line 



* --- AUTOMATED DIAGNOSTIC PRINTS ---

* --- Device m5 ---
.print dc
+ lv1(XU1.XCORE.m5) lv2(XU1.XCORE.m5) lx2(XU1.XCORE.m5)  lx3(XU1.XCORE.m5)  par('abs(lx1(XU1.XCORE.m5))') 
+ i(XU1.XCORE.m5)    par('abs(i(XU1.XCORE.m5))') lx7(XU1.XCORE.m5) lx8(XU1.XCORE.m5) lx9(XU1.XCORE.m5) 
+ par('lx7(XU1.XCORE.m5)/max(abs(i(XU1.XCORE.m5)),1e-15)')
+ lv9(XU1.XCORE.m5)  lv10(XU1.XCORE.m5) lv13(XU1.XCORE.m5) lv22(XU1.XCORE.m5) lv21(XU1.XCORE.m5)
+ lx18(XU1.XCORE.m5) lx19(XU1.XCORE.m5) lx20(XU1.XCORE.m5) lx21(XU1.XCORE.m5) lx22(XU1.XCORE.m5) 
+ lx23(XU1.XCORE.m5) lx32(XU1.XCORE.m5) lx33(XU1.XCORE.m5) lx34(XU1.XCORE.m5)
+ lx82(XU1.XCORE.m5) lx83(XU1.XCORE.m5) lx84(XU1.XCORE.m5) lx85(XU1.XCORE.m5) lx86(XU1.XCORE.m5) 
+ lx89(XU1.XCORE.m5) lx90(XU1.XCORE.m5) lx287(XU1.XCORE.m5)

* --- Device m4 ---
.print dc
+ lv1(XU1.XCORE.m4) lv2(XU1.XCORE.m4) lx2(XU1.XCORE.m4)  lx3(XU1.XCORE.m4)  par('abs(lx1(XU1.XCORE.m4))') 
+ i(XU1.XCORE.m4)    par('abs(i(XU1.XCORE.m4))') lx7(XU1.XCORE.m4) lx8(XU1.XCORE.m4) lx9(XU1.XCORE.m4) 
+ par('lx7(XU1.XCORE.m4)/max(abs(i(XU1.XCORE.m4)),1e-15)')
+ lv9(XU1.XCORE.m4)  lv10(XU1.XCORE.m4) lv13(XU1.XCORE.m4) lv22(XU1.XCORE.m4) lv21(XU1.XCORE.m4)
+ lx18(XU1.XCORE.m4) lx19(XU1.XCORE.m4) lx20(XU1.XCORE.m4) lx21(XU1.XCORE.m4) lx22(XU1.XCORE.m4) 
+ lx23(XU1.XCORE.m4) lx32(XU1.XCORE.m4) lx33(XU1.XCORE.m4) lx34(XU1.XCORE.m4)
+ lx82(XU1.XCORE.m4) lx83(XU1.XCORE.m4) lx84(XU1.XCORE.m4) lx85(XU1.XCORE.m4) lx86(XU1.XCORE.m4) 
+ lx89(XU1.XCORE.m4) lx90(XU1.XCORE.m4) lx287(XU1.XCORE.m4)

* --- Device m2 ---
.print dc
+ lv1(XU1.XCORE.m2) lv2(XU1.XCORE.m2) lx2(XU1.XCORE.m2)  lx3(XU1.XCORE.m2)  par('abs(lx1(XU1.XCORE.m2))') 
+ i(XU1.XCORE.m2)    par('abs(i(XU1.XCORE.m2))') lx7(XU1.XCORE.m2) lx8(XU1.XCORE.m2) lx9(XU1.XCORE.m2) 
+ par('lx7(XU1.XCORE.m2)/max(abs(i(XU1.XCORE.m2)),1e-15)')
+ lv9(XU1.XCORE.m2)  lv10(XU1.XCORE.m2) lv13(XU1.XCORE.m2) lv22(XU1.XCORE.m2) lv21(XU1.XCORE.m2)
+ lx18(XU1.XCORE.m2) lx19(XU1.XCORE.m2) lx20(XU1.XCORE.m2) lx21(XU1.XCORE.m2) lx22(XU1.XCORE.m2) 
+ lx23(XU1.XCORE.m2) lx32(XU1.XCORE.m2) lx33(XU1.XCORE.m2) lx34(XU1.XCORE.m2)
+ lx82(XU1.XCORE.m2) lx83(XU1.XCORE.m2) lx84(XU1.XCORE.m2) lx85(XU1.XCORE.m2) lx86(XU1.XCORE.m2) 
+ lx89(XU1.XCORE.m2) lx90(XU1.XCORE.m2) lx287(XU1.XCORE.m2)

* --- Device m0 ---
.print dc
+ lv1(XU1.XCORE.m0) lv2(XU1.XCORE.m0) lx2(XU1.XCORE.m0)  lx3(XU1.XCORE.m0)  par('abs(lx1(XU1.XCORE.m0))') 
+ i(XU1.XCORE.m0)    par('abs(i(XU1.XCORE.m0))') lx7(XU1.XCORE.m0) lx8(XU1.XCORE.m0) lx9(XU1.XCORE.m0) 
+ par('lx7(XU1.XCORE.m0)/max(abs(i(XU1.XCORE.m0)),1e-15)')
+ lv9(XU1.XCORE.m0)  lv10(XU1.XCORE.m0) lv13(XU1.XCORE.m0) lv22(XU1.XCORE.m0) lv21(XU1.XCORE.m0)
+ lx18(XU1.XCORE.m0) lx19(XU1.XCORE.m0) lx20(XU1.XCORE.m0) lx21(XU1.XCORE.m0) lx22(XU1.XCORE.m0) 
+ lx23(XU1.XCORE.m0) lx32(XU1.XCORE.m0) lx33(XU1.XCORE.m0) lx34(XU1.XCORE.m0)
+ lx82(XU1.XCORE.m0) lx83(XU1.XCORE.m0) lx84(XU1.XCORE.m0) lx85(XU1.XCORE.m0) lx86(XU1.XCORE.m0) 
+ lx89(XU1.XCORE.m0) lx90(XU1.XCORE.m0) lx287(XU1.XCORE.m0)

* --- Device m3 ---
.print dc
+ lv1(XU1.XCORE.m3) lv2(XU1.XCORE.m3) lx2(XU1.XCORE.m3)  lx3(XU1.XCORE.m3)  par('abs(lx1(XU1.XCORE.m3))') 
+ i(XU1.XCORE.m3)    par('abs(i(XU1.XCORE.m3))') lx7(XU1.XCORE.m3) lx8(XU1.XCORE.m3) lx9(XU1.XCORE.m3) 
+ par('lx7(XU1.XCORE.m3)/max(abs(i(XU1.XCORE.m3)),1e-15)')
+ lv9(XU1.XCORE.m3)  lv10(XU1.XCORE.m3) lv13(XU1.XCORE.m3) lv22(XU1.XCORE.m3) lv21(XU1.XCORE.m3)
+ lx18(XU1.XCORE.m3) lx19(XU1.XCORE.m3) lx20(XU1.XCORE.m3) lx21(XU1.XCORE.m3) lx22(XU1.XCORE.m3) 
+ lx23(XU1.XCORE.m3) lx32(XU1.XCORE.m3) lx33(XU1.XCORE.m3) lx34(XU1.XCORE.m3)
+ lx82(XU1.XCORE.m3) lx83(XU1.XCORE.m3) lx84(XU1.XCORE.m3) lx85(XU1.XCORE.m3) lx86(XU1.XCORE.m3) 
+ lx89(XU1.XCORE.m3) lx90(XU1.XCORE.m3) lx287(XU1.XCORE.m3)

* --- Device m1 ---
.print dc
+ lv1(XU1.XCORE.m1) lv2(XU1.XCORE.m1) lx2(XU1.XCORE.m1)  lx3(XU1.XCORE.m1)  par('abs(lx1(XU1.XCORE.m1))') 
+ i(XU1.XCORE.m1)    par('abs(i(XU1.XCORE.m1))') lx7(XU1.XCORE.m1) lx8(XU1.XCORE.m1) lx9(XU1.XCORE.m1) 
+ par('lx7(XU1.XCORE.m1)/max(abs(i(XU1.XCORE.m1)),1e-15)')
+ lv9(XU1.XCORE.m1)  lv10(XU1.XCORE.m1) lv13(XU1.XCORE.m1) lv22(XU1.XCORE.m1) lv21(XU1.XCORE.m1)
+ lx18(XU1.XCORE.m1) lx19(XU1.XCORE.m1) lx20(XU1.XCORE.m1) lx21(XU1.XCORE.m1) lx22(XU1.XCORE.m1) 
+ lx23(XU1.XCORE.m1) lx32(XU1.XCORE.m1) lx33(XU1.XCORE.m1) lx34(XU1.XCORE.m1)
+ lx82(XU1.XCORE.m1) lx83(XU1.XCORE.m1) lx84(XU1.XCORE.m1) lx85(XU1.XCORE.m1) lx86(XU1.XCORE.m1) 
+ lx89(XU1.XCORE.m1) lx90(XU1.XCORE.m1) lx287(XU1.XCORE.m1)

.end
