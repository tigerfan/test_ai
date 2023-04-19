/*
 * 使用K型热电偶测量4路分层温度，冷端温度使用LMT70A测量。
 * 冷端信号进行模数转换后计算出冷端温度，由冷端温度计算出对应热电偶电势值，再与输入电压相加后，计算求得分层温度值。
 * K型热电偶电势与温度对应函数与反函数公式由NIST ITS-90标准给出。
 * LMT70A依据TI提供的3阶多项式进行计算。
 *
 * 本文定义热电势到温度转换的表格数据。
 * by tigerfan, 2023.4
 */
package mylib

import spinal.core._

class Thermocouples extends Component {
  val io = new Bundle {
    val adcThermo = in SInt(16 bits)
	  val coldResult = in SInt(16 bits)
    val hotValue = out SInt(16 bits)
  }

  def hotTable = for(idx <- 0 until 65536) yield {
    val e = Array[Double](0.0000000E+00, 2.5173462E+01, -1.1662878E+00, -1.0833638E+00, -8.9773540E-01, -3.7342377E-01, -8.6632643E-02, -1.0450598E-02, -5.1920577E-04, 0.0000000E+00)
    val f = Array[Double](0.000000E+00, 2.508355E+01, 7.860106E-02, -2.503131E-01, 8.315270E-02, -1.228034E-02, 9.804036E-04, -4.413030E-05, 1.057734E-06, -1.052755E-08)
    val g = Array[Double](-1.318058E+02, 4.830222E+01, -1.646031E+00, 5.464731E-02, -9.650715E-04, 8.802193E-06, -3.110810E-08, 0.000000E+00, 0.000000E+00, 0.000000E+00)

    //前端信号调理电路对热电偶电势值放大了约89倍
	//冷端电势通过乘法运算放大同等比例
    val gain = 89.0

    //16位模数转换器全范围-5V~+5V
    //拟合多项式电势值单位为mv
    var voltmv = 0.0
    if (idx < 32768) {
      voltmv = idx * 5000.0 / (32768 * gain)
    } else {
      voltmv = (idx - 65536) * 5000.0 / (32768 * gain)
    }

    //温度超限时取上下边界值，此处理方法副作用可预期，以避免未知异常引发故障
    var hotValue = 0.0
    if (voltmv <= -5.891) {
      hotValue = -200.0
    } else if (voltmv < 0) {
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
    } else if (voltmv >= 54.886) {
      hotValue = 1372.0
    }

    //打印表格数据
    println(idx, voltmv, hotValue)

    //LSB代表0.05°
    val multiplier = 20
    S((hotValue * multiplier).toInt, 16 bits)
  }

  val hotRom =  Mem(SInt(16 bits),initialContent = hotTable)
  //与处理后的冷端电势作饱和加后查表
  io.hotValue := hotRom.readSync(U(io.adcThermo +| io.coldResult))

}

//Generate the MyThermo's Verilog
object MyThermoVerilog {
  def main(args: Array[String]) {
    SpinalVerilog(new Thermocouples).printPruned()
  }
}
