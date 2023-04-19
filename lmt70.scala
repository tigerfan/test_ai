/*
 * 使用K型热电偶测量4路分层温度，冷端温度使用LMT70A测量。
 * 冷端信号进行模数转换后计算出冷端温度，由冷端温度计算出对应热电偶电势值，再与输入电压相加后，计算求得分层温度值。
 * K型热电偶电势与温度对应函数与反函数公式由NIST ITS-90标准给出。
 * LMT70A依据TI提供的3阶多项式进行计算。
 *
 * 本文定义冷端电势到冷端温度再到对应热电偶电势值的转换表格。
 * by tigerfan, 2023.4
 */
package mylib

import spinal.core._

class LMT70A extends Component {
  val io = new Bundle {
    val adcResult = in UInt(16 bits)
    val coldVolt = out SInt(16 bits)
  }

  def coldTable = for(idx <- 0 until 65536) yield {
    val a0 = -1.064200E-09
    val a1 = -5.759725E-06
    val a2 = -1.789883E-01
    val a3 = 2.048570E+02

    //16位模数转换器全范围-5V~+5V
    //拟合多项式电势值单位为mv
    var voltmv = 0.0
    if(idx < 32768) {
      voltmv = idx * 5000.0 / 32768
    } else {
      voltmv = (idx - 65536) * 5000.0 / 32768
    }

    var coldTemperature = a0 * Math.pow(voltmv, 3) + a1 * Math.pow(voltmv, 2) + a2 * voltmv + a3

    //冷端温度超限时取上下边界值，此处理方法副作用可预期，以避免未知异常引发故障
    if (coldTemperature > 150.0) {
      coldTemperature = 150.0
    } else if (coldTemperature < -55.0) {
      coldTemperature = -55.0
    }

    var coldVoltmv = 0.0
    if (coldTemperature < 0) {
      val b = Array[Double](0.000000000000E+00, 0.394501280250E-01, 0.236223735980E-04, -0.328589067840E-06, -0.499048287770E-08, -0.675090591730E-10, -0.574103274280E-12, -0.310888728940E-14, -0.104516093650E-16, -0.198892668780E-19, -0.163226974860E-22)
      for (i <- 0 to 10) {
        coldVoltmv += b(i) * Math.pow(coldTemperature, i)
      }
    } else {
      val c = Array[Double](-0.176004136860E-01, 0.389212049750E-01, 0.185587700320E-04, -0.994575928740E-07, 0.318409457190E-09, -0.560728448890E-12, 0.560750590590E-15, -0.320207200030E-18, 0.971511471520E-22, -0.121047212750E-25)
      val d0 = 0.118597600000E+00
      val d1 = -0.118343200000E-03
      val d2 = 0.126968600000E+03
      for (i <- 0 to 9) {
        coldVoltmv += c(i) * Math.pow(coldTemperature, i)
      }
      coldVoltmv += d0 * Math.exp(d1 * Math.pow(coldTemperature - d2, 2))
    }

    //打印表格数据
    println(idx, voltmv, coldTemperature, coldVoltmv)

    //放大倍数与热电偶输入范围对齐
	  val gain = 89.0
	  S((coldVoltmv * gain * 32768 / 5000 ).toInt, 16 bits)
  }

  val coldRom =  Mem(SInt(16 bits),initialContent = coldTable)
  io.coldVolt := coldRom.readSync(io.adcResult)

}

//Generate the MyLMT's Verilog
object MyLMTVerilog {
  def main(args: Array[String]) {
    SpinalVerilog(new LMT70A).printPruned()
  }
}
