package com.projectci.insurance;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
//@ActiveProfiles("mqtt") // Или "mqtt", чтобы тест "видел" хотя бы один бин Publisher
class InsuranceApplicationTests {

	@Test
	void contextLoads() {
	}

}
