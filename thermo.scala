/*
 * 使用K型热电偶测量4路分层温度，冷端温度使用LMT70A测量。
 * 冷端信号进行模数转换后计算出冷端温度，由冷端温度计算出对应热电偶电势值，再与输入电压相加后，计算求得分层温度值。
 * K型热电偶电势与温度对应函数与反函数公式由NIST ITS-90标准给出。
 * LMT70A依据TI提供的3阶多项式进行计算。
 */
package mylib

import spinal.core._
import spinal.lib._
import spinal.lib.fsm._

class Thermocouples extends Component {
  val io = new Bundle {
    val adcThermo = in UInt(16 bits)
    val hotValue = out SInt(16 bits)
  }

  def hotTable = for(idx <- -32768 until 32767) yield {
    val e = Array[Double](0.0000000E+00, 2.5173462E+01, -1.1662878E+00, -1.0833638E+00, -8.9773540E-01, -3.7342377E-01, -8.6632643E-02, -1.0450598E-02, -5.1920577E-04, 0.0000000E+00)
    val f = Array[Double](0.000000E+00, 2.508355E+01, 7.860106E-02, -2.503131E-01, 8.315270E-02, -1.228034E-02, 9.804036E-04, -4.413030E-05, 1.057734E-06, -1.052755E-08)
    val g = Array[Double](-1.318058E+02, 4.830222E+01, -1.646031E+00, 5.464731E-02, -9.650715E-04, 8.802193E-06, -3.110810E-08, 0.000000E+00, 0.000000E+00, 0.000000E+00)
    val gain = 89.0

    var voltmv = idx * 5000.0 / (65536 * gain)

    if (voltmv < -5.891) {
      voltmv = -5.891
    } else if (voltmv > 54.886) {
      voltmv = 54.886
    }

    var hotValue = 0.0
    if (voltmv < 0) {
      for (i <- 0 to 9) {
        hotValue += e(i) * Math.pow(voltmv, i)
      }
    } else if (voltmv < 20.644) {
       for (i <- 0 to 9) {
        hotValue += f(i) * Math.pow(voltmv, i)
      }
    } else if (voltmv < 54.886) {
      for (i <- 0 to 9) {
        hotValue += g(i) * Math.pow(voltmv, i)
      }
    }

    S((hotValue * 20).toInt, 16 bits)
  }

  val hotRom =  Mem(SInt(16 bits),initialContent = hotTable)
  io.hotValue := hotRom.readSync(io.adcThermo)

}

//Generate the MyThermo's Verilog
object MyThermoVerilog {
  def main(args: Array[String]) {
    SpinalVerilog(new Thermocouples).printPruned()
  }
}
