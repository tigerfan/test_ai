from amaranth import *
from amaranth.lib import wiring, data, stream
from amaranth.lib.wiring import connect
from amaranth.lib.fifo import SyncFIFOBuffered

class AD7606DataAcquisition(Elaboratable):
    def __init__(self):
        # 3片AD7606，每片8通道，共24路输入信号
        self.adc_data = [Signal(16, name=f"adc_data_{i}") for i in range(24)]
        self.adc_data_regs = [Signal(16, name=f"adc_data_reg_{i}") for i in range(24)]
        self.adc_busy = Signal(3)  # 3片AD7606的忙碌信号
        self.adc_convst = Signal(3)  # 转换启动信号
        self.adc_reset = Signal(3)  # 复位信号
        self.adc_data_valid = Signal(3)  # 数据有效信号

        # 双端口缓冲区，乒乓模式
        self.buffer_size = 1024  # 假设缓冲区大小为1024个样本
        self.half_buffer_size = self.buffer_size // 2
        self.buffer = Memory(width=16, depth=self.buffer_size * 24)
        self.read_port = self.buffer.read_port(transparent=True)
        self.write_port = self.buffer.write_port()

        # FSMC接口信号
        self.fsmc_data = Signal(16)
        self.fsmc_addr = Signal(10)  # 假设地址宽度为10位
        self.fsmc_rd = Signal()
        self.fsmc_wr = Signal()
        self.fsmc_cs = Signal()

        # 中断信号
        self.irq_upper_half = Signal()
        self.irq_lower_half = Signal()

        # 内部状态
        self.write_pointer = Signal(range(self.buffer_size * 24), reset=0)
        self.read_pointer = Signal(range(self.buffer_size * 24), reset=0)
        self.current_half = Signal()  # 0表示上半区，1表示下半区
        self.write_counter = Signal(range(25))  # 用于序列化写入24个通道
        self.write_debug_counter = Signal(range(25), reset=0)  # 调试信号，跟踪成功写入次数
        self.last_written_data = [Signal(16, name=f"last_written_data_{i}", reset=0) for i in range(24)]  # 存储最近写入的数据用于调试

    def elaborate(self, platform):
        m = Module()

        # AD7606控制逻辑
        adc_convst_internal = Signal(3)
        for i in range(3):
            m.d.comb += self.adc_convst[i].eq(adc_convst_internal[i] & ~self.adc_busy[i])
            m.d.comb += self.adc_reset[i].eq(0)  # 假设复位信号为低有效

        # 数据采集逻辑
        with m.FSM() as fsm:
            with m.State("IDLE"):
                m.d.sync += adc_convst_internal.eq(0b111)  # 启动所有AD7606转换
                m.next = "WAIT_FOR_CONVERSION"

            with m.State("WAIT_FOR_CONVERSION"):
                m.d.sync += adc_convst_internal.eq(0)  # 关闭转换信号
                with m.If(self.adc_busy == 0):
                    m.next = "READ_DATA"

            with m.State("READ_DATA"):
                with m.If(self.adc_data_valid == 0b111):
                    for i in range(24):
                        m.d.sync += self.adc_data_regs[i].eq(self.adc_data[i])
                    m.d.sync += self.write_counter.eq(0)
                    m.next = "WRITE_DATA"
                with m.Else():
                    m.d.sync += self.write_port.en.eq(0)

            with m.State("WRITE_DATA"):
                with m.If(self.write_counter < 24):
                    m.d.sync += self.write_port.addr.eq(self.write_pointer + self.write_counter)
                    # 使用组合逻辑选择要写入的数据
                    current_data = Signal(16, name="current_write_data")
                    with m.Switch(self.write_counter):
                        for i in range(24):
                            with m.Case(i):
                                m.d.comb += current_data.eq(self.adc_data_regs[i])
                    m.d.sync += self.write_port.data.eq(current_data)
                    m.d.sync += self.write_port.en.eq(1)  # 确保启用写入
                    m.d.sync += self.write_counter.eq(self.write_counter + 1)
                    m.d.sync += self.write_debug_counter.eq(self.write_debug_counter + 1)  # 增加调试计数器
                    # 使用Switch语句更新last_written_data数组
                    with m.Switch(self.write_counter):
                        for i in range(24):
                            with m.Case(i):
                                m.d.sync += self.last_written_data[i].eq(current_data)
                with m.Else():
                    m.d.sync += self.write_port.en.eq(0)  # 禁用写入
                    m.d.sync += self.write_pointer.eq(self.write_pointer + 24)
                    m.d.sync += self.write_counter.eq(0)
                    with m.If(self.write_pointer >= (self.half_buffer_size * 24)):
                        m.d.sync += self.current_half.eq(1)
                        m.d.sync += self.irq_upper_half.eq(1)
                        m.d.sync += self.irq_lower_half.eq(0)  # 清除下半部分中断，当写入指针进入上半区时
                    with m.Else():
                        m.d.sync += self.current_half.eq(0)
                        m.d.sync += self.irq_lower_half.eq(1)
                        m.d.sync += self.irq_upper_half.eq(0)  # 清除上半部分中断，当写入指针在下半区时
                    m.next = "WRITE_DELAY"

            with m.State("WRITE_DELAY"):
                # 添加一个延迟状态，确保数据被写入内存
                delay_counter = Signal(4, reset=0)
                m.d.sync += delay_counter.eq(delay_counter + 1)
                with m.If(delay_counter >= 10):  # 延迟10个时钟周期
                    m.d.sync += delay_counter.eq(0)
                    m.next = "IDLE"

            with m.State("CHECK_BUFFER"):
                with m.If(self.write_pointer >= self.half_buffer_size * 24):
                    m.d.sync += self.current_half.eq(1)
                    with m.If(self.read_pointer < self.half_buffer_size * 24):
                        m.d.sync += self.irq_upper_half.eq(1)  # 触发上半区中断，只有当读指针在上半区时
                    m.d.sync += self.irq_lower_half.eq(0)
                with m.Else():
                    m.d.sync += self.current_half.eq(0)
                    with m.If(self.read_pointer >= self.half_buffer_size * 24):
                        m.d.sync += self.irq_lower_half.eq(1)  # 触发下半区中断，只有当读指针在下半区时
                    m.d.sync += self.irq_upper_half.eq(0)
                with m.If(self.write_pointer >= self.buffer_size * 24):
                    m.d.sync += self.write_pointer.eq(0)  # 缓冲区满，循环回开始
                m.next = "IDLE"

        # FSMC接口逻辑
        with m.If((self.fsmc_cs == 0) & (self.fsmc_rd == 0)):
            m.d.comb += self.read_port.addr.eq(self.read_pointer)
            # 使用存储的最近写入数据而不是直接从内存读取，用于调试
            debug_data = Signal(16, name="debug_read_data")
            read_index = Signal(range(24), name="read_index")
            m.d.comb += read_index.eq(self.read_pointer - (self.read_pointer // 24) * 24)
            with m.Switch(read_index):
                for i in range(24):
                    with m.Case(i):
                        m.d.comb += debug_data.eq(self.last_written_data[i])
            m.d.comb += self.fsmc_data.eq(debug_data)
            # 只有在实际读取操作完成后才增加读指针
            m.d.sync += self.read_pointer.eq(self.read_pointer + 1)
            with m.If(self.read_pointer >= self.buffer_size * 24 - 1):
                m.d.sync += self.read_pointer.eq(0)
            with m.If(self.read_pointer == (self.half_buffer_size * 24 - 1)):
                m.d.sync += self.irq_upper_half.eq(0)  # 清除上半区中断
            with m.If(self.read_pointer == (self.buffer_size * 24 - 1)):
                m.d.sync += self.irq_lower_half.eq(0)  # 清除下半区中断
        with m.Else():
            m.d.comb += self.fsmc_data.eq(0)  # 当不读取时输出0

        return m
